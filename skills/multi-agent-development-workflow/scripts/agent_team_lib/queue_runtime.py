from __future__ import annotations

import os
from pathlib import Path
import subprocess
import time
import uuid

from .core import (
    FileLock, OrchestratorError, process_alive, project_fingerprint, project_lock_path,
    project_runtime_root,
    read_json, task_runtime_dir, write_json_atomic,
)
from .processes import (
    choose_runtime, process_identity, process_identity_matches,
    run_codex, run_pi_rpc, terminate_pid_group,
)

LEASE_SECONDS = 20


def child_process_quiesced(pid: int) -> bool:
    if not process_alive(pid):
        return True
    if os.name == "posix":
        try:
            result = subprocess.run(
                ["ps", "-o", "stat=", "-p", str(pid)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            state = result.stdout.strip()
            if not state or state.startswith("Z"):
                return True
        except OSError:
            pass
    return False


def queue_root(root: Path, project_root: Path) -> Path:
    return project_runtime_root(root, project_root) / "queue"


def queue_paths(root: Path, project_root: Path, role: str) -> dict[str, Path]:
    base = queue_root(root, project_root)
    paths = {
        "queued": base / "queued" / role.lower(),
        "claimed": base / "claimed" / role.lower(),
        "results": base / "results",
        "cancelled": base / "cancelled",
        "quarantined": base / "quarantined" / role.lower(),
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def workers_dir(root: Path, project_root: Path) -> Path:
    path = project_runtime_root(root, project_root) / "workers"
    path.mkdir(parents=True, exist_ok=True)
    return path


def heartbeat_path(root: Path, project_root: Path, role: str) -> Path:
    return workers_dir(root, project_root) / f"{role.lower()}.json"


def worker_available(root: Path, project_root: Path, role: str) -> bool:
    path = heartbeat_path(root, project_root, role)
    if not path.exists():
        return False
    try:
        data = read_json(path)
        return (
            data.get("project_fingerprint") == project_fingerprint(project_root)
            and process_alive(int(data["pid"]))
        )
    except Exception:
        return False


def cancellation_path(root: Path, project_root: Path, job_id: str) -> Path:
    return queue_root(root, project_root) / "cancelled" / f"{job_id}.json"


def request_cancel(root: Path, project_root: Path, job_id: str, reason: str) -> None:
    write_json_atomic(cancellation_path(root, project_root, job_id), {
        "job_id": job_id,
        "cancelled_at": time.time(),
        "reason": reason,
    })


def is_cancelled(root: Path, project_root: Path, job_id: str) -> bool:
    return cancellation_path(root, project_root, job_id).exists()


def quarantine_claim(
    root: Path, project_root: Path, role: str, claim: Path, reason: str,
) -> Path:
    paths = queue_paths(root, project_root, role)
    target = paths["quarantined"] / claim.name
    try:
        os.replace(claim, target)
    except FileNotFoundError:
        target = paths["quarantined"] / f"missing-{int(time.time() * 1000)}.json"
    write_json_atomic(target.with_suffix(target.suffix + ".error.json"), {
        "claim": target.name,
        "reason": reason,
        "quarantined_at": time.time(),
    })
    write_json_atomic(shared_orphan_risk_path(root, project_root), {
        "claim": str(target), "reason": reason, "quarantined_at": time.time(),
    })
    return target


def quarantined_jobs(root: Path, project_root: Path) -> list[Path]:
    base = queue_root(root, project_root) / "quarantined"
    if not base.exists():
        return []
    return sorted(
        p for p in base.rglob("*.json")
        if not p.name.endswith(".error.json")
    )


def shared_orphan_risk_path(root: Path, project_root: Path) -> Path:
    return project_lock_path(root, project_root).with_name("agent-team-orphan-risk.json")


def require_no_quarantined_jobs(root: Path, project_root: Path) -> None:
    jobs = quarantined_jobs(root, project_root)
    shared = shared_orphan_risk_path(root, project_root)
    if shared.exists():
        jobs.append(shared)
    if jobs:
        raise OrchestratorError(
            "Queue contains quarantined claims with UNKNOWN_ORPHAN_RISK. "
            f"Inspect before continuing: {[str(p) for p in jobs]}"
        )


def recover_expired_claims(root: Path, project_root: Path, role: str) -> None:
    paths = queue_paths(root, project_root, role)
    now = time.time()
    for claim in sorted(paths["claimed"].glob("*.json")):
        try:
            data = read_json(claim)
        except Exception as exc:
            quarantine_claim(
                root, project_root, role, claim,
                f"Malformed/unreadable claimed job: {exc}",
            )
            continue

        try:
            if float(data.get("lease_until", 0)) > now:
                continue
        except (TypeError, ValueError):
            quarantine_claim(
                root, project_root, role, claim,
                "Claim has invalid lease_until.",
            )
            continue

        job_id = str(data.get("job_id") or claim.stem)
        child_pid = data.get("child_pid")
        if not child_pid:
            quarantine_claim(
                root, project_root, role, claim,
                "UNKNOWN_ORPHAN_RISK: expired claim has no recorded child_pid.",
            )
            continue

        try:
            pid = int(child_pid)
        except (TypeError, ValueError):
            quarantine_claim(
                root, project_root, role, claim,
                "UNKNOWN_ORPHAN_RISK: invalid child_pid.",
            )
            continue

        if not child_process_quiesced(pid):
            identity = data.get("child_identity")
            if not isinstance(identity, dict) or not process_identity_matches(identity):
                quarantine_claim(
                    root, project_root, role, claim,
                    f"UNKNOWN_PROCESS_IDENTITY: live PID {pid} does not match recorded child identity.",
                )
                continue
            terminate_pid_group(pid, grace=1.0)
        if not child_process_quiesced(pid):
            quarantine_claim(
                root, project_root, role, claim,
                f"UNKNOWN_ORPHAN_RISK: child process {pid} could not be quiesced.",
            )
            continue

        if is_cancelled(root, project_root, job_id):
            write_json_atomic(paths["results"] / f"{job_id}.json", {
                "job_id": job_id,
                "success": False,
                "cancelled": True,
                "error": "Recovered expired cancelled claim.",
            })
            claim.unlink(missing_ok=True)
            continue

        for key in ("lease_owner", "lease_until", "child_pid", "child_identity"):
            data.pop(key, None)
        data["state"] = "QUEUED"
        write_json_atomic(paths["queued"] / f"{job_id}.json", data)
        claim.unlink(missing_ok=True)

def claim_next_job(root: Path, project_root: Path, role: str, worker_id: str) -> Path | None:
    paths = queue_paths(root, project_root, role)
    recover_expired_claims(root, project_root, role)
    for job_path in sorted(paths["queued"].glob("*.json")):
        job_id = job_path.stem
        if is_cancelled(root, project_root, job_id):
            job_path.unlink(missing_ok=True)
            write_json_atomic(paths["results"] / f"{job_id}.json", {
                "job_id": job_id,
                "success": False,
                "cancelled": True,
                "error": "Cancelled before claim.",
            })
            continue

        claimed = paths["claimed"] / job_path.name
        try:
            os.replace(job_path, claimed)
        except FileNotFoundError:
            continue

        data = read_json(claimed)
        data.update({
            "state": "CLAIMED",
            "lease_owner": worker_id,
            "lease_until": time.time() + LEASE_SECONDS,
        })
        write_json_atomic(claimed, data)
        return claimed
    return None


def renew_claim(
    claim: Path,
    worker_id: str,
    child_pid: int | None = None,
    child_identity: dict[str, object] | None = None,
) -> None:
    data = read_json(claim)
    if data.get("lease_owner") != worker_id:
        raise OrchestratorError("Queue lease ownership changed unexpectedly.")
    data["state"] = "RUNNING"
    data["lease_until"] = time.time() + LEASE_SECONDS
    if child_pid:
        data["child_pid"] = child_pid
    if child_identity:
        data["child_identity"] = child_identity
    write_json_atomic(claim, data)


def cancel_and_quiesce_job(
    root: Path, project_root: Path, role: str, job_id: str,
    reason: str, wait_seconds: float = 5.0,
) -> None:
    paths = queue_paths(root, project_root, role)
    request_cancel(root, project_root, job_id, reason)
    (paths["queued"] / f"{job_id}.json").unlink(missing_ok=True)

    claim = paths["claimed"] / f"{job_id}.json"
    if claim.exists():
        try:
            child_pid = read_json(claim).get("child_pid")
            if not child_pid:
                quarantine_claim(
                    root, project_root, role, claim,
                    "UNKNOWN_ORPHAN_RISK: cancellation found no recorded child_pid.",
                )
                raise OrchestratorError(
                    f"Queue job {job_id} quarantined: child process identity is unknown."
                )
            if not child_process_quiesced(int(child_pid)):
                data = read_json(claim)
                identity = data.get("child_identity")
                if not isinstance(identity, dict) or not process_identity_matches(identity):
                    quarantine_claim(
                        root, project_root, role, claim,
                        f"UNKNOWN_PROCESS_IDENTITY: live PID {child_pid} does not match recorded child identity.",
                    )
                    raise OrchestratorError(
                        f"Queue job {job_id} quarantined: process identity cannot be proven."
                    )
                terminate_pid_group(int(child_pid), grace=1.0)
            if not child_process_quiesced(int(child_pid)):
                quarantine_claim(
                    root, project_root, role, claim,
                    f"UNKNOWN_ORPHAN_RISK: child process {child_pid} survived cancellation.",
                )
                raise OrchestratorError(
                    f"Queue job {job_id} quarantined: child process could not be stopped."
                )
        except OrchestratorError:
            raise
        except Exception as exc:
            quarantine_claim(
                root, project_root, role, claim,
                f"Cancellation could not inspect claimed job: {exc}",
            )
            raise OrchestratorError(
                f"Queue job {job_id} quarantined during cancellation."
            ) from exc

    result_path = paths["results"] / f"{job_id}.json"
    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        if result_path.exists():
            result_path.unlink(missing_ok=True)
            return
        if not claim.exists():
            return
        time.sleep(0.1)


def queue_dispatch(
    runtime: str, role: str, prompt: str, project_root: Path,
    root: Path, task_id: str, timeout: int,
) -> None:
    if not worker_available(root, project_root, role):
        raise OrchestratorError(f"No {role} pane worker for project {project_root} is running.")

    paths = queue_paths(root, project_root, role)
    job_id = f"{int(time.time() * 1000)}-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    write_json_atomic(paths["queued"] / f"{job_id}.json", {
        "job_id": job_id,
        "state": "QUEUED",
        "runtime": runtime,
        "role": role,
        "prompt": prompt,
        "project_root": str(project_root.resolve()),
        "project_fingerprint": project_fingerprint(project_root),
        "task_id": task_id,
        "timeout": timeout,
        "created_at": time.time(),
    })

    result_path = paths["results"] / f"{job_id}.json"
    deadline = time.monotonic() + timeout + 15
    try:
        while time.monotonic() < deadline:
            if result_path.exists():
                result = read_json(result_path)
                result_path.unlink(missing_ok=True)
                if result.get("success"):
                    return
                raise OrchestratorError(
                    f"{role} queue worker failed: {result.get('error', 'unknown error')}"
                )
            if not worker_available(root, project_root, role):
                raise OrchestratorError(
                    f"{role} pane worker disappeared while {job_id} was pending."
                )
            time.sleep(0.5)
        raise OrchestratorError(f"Timed out waiting for {role} queue job {job_id}.")
    except BaseException as exc:
        cancel_and_quiesce_job(
            root, project_root, role, job_id, str(exc)
        )
        raise


def worker_loop(
    project_root: Path, root: Path, role: str, default_runtime: str,
    once: bool, poll_seconds: float,
) -> int:
    worker_id = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
    heartbeat = heartbeat_path(root, project_root, role)
    registration_lock = workers_dir(root, project_root) / f".{role.lower()}.register.lock"
    with FileLock(registration_lock, f"{role} worker registration"):
        if worker_available(root, project_root, role):
            raise OrchestratorError(
                f"A {role} pane worker is already running for this project."
            )
        write_json_atomic(heartbeat, {
            "pid": os.getpid(),
            "worker_id": worker_id,
            "role": role,
            "project_root": str(project_root),
            "project_fingerprint": project_fingerprint(project_root),
            "started_at": time.time(),
        })

    require_no_quarantined_jobs(root, project_root)

    try:
        while True:
            recover_expired_claims(root, project_root, role)
            require_no_quarantined_jobs(root, project_root)
            claim = claim_next_job(root, project_root, role, worker_id)
            if claim is None:
                if once:
                    return 0
                heartbeat.touch()
                time.sleep(poll_seconds)
                continue

            job_id = claim.stem
            try:
                job = read_json(claim)
                job_id = str(job.get("job_id", job_id))

                if job.get("project_fingerprint") != project_fingerprint(project_root):
                    raise OrchestratorError("Queue job project fingerprint mismatch.")

                job_root = Path(job["project_root"]).resolve()
                if job_root != project_root.resolve():
                    raise OrchestratorError(
                        f"Queue job project root mismatch: {job_root} != {project_root}"
                    )

                runtime = choose_runtime(job.get("runtime", default_runtime))
                timeout = int(job.get("timeout", 3600))
                log_path = task_runtime_dir(
                    root, project_root, job["task_id"]
                ) / f"{role.lower()}.log"

                child_identity_cache: dict[str, object] | None = None

                def tick(proc: subprocess.Popen) -> None:
                    nonlocal child_identity_cache
                    if child_identity_cache is None:
                        child_identity_cache = process_identity(proc.pid)
                    renew_claim(
                        claim,
                        worker_id,
                        proc.pid,
                        child_identity=child_identity_cache,
                    )
                    heartbeat.touch()

                cancelled = lambda: is_cancelled(root, project_root, job_id)
                if cancelled():
                    raise OrchestratorError("Queue job cancelled before execution.")

                if runtime == "codex":
                    run_codex(
                        job["prompt"], job_root, log_path, role, timeout,
                        tick=tick, cancelled=cancelled,
                    )
                elif runtime == "pi":
                    run_pi_rpc(
                        job["prompt"], job_root, log_path, role, timeout,
                        tick=tick, cancelled=cancelled,
                    )
                else:
                    raise OrchestratorError(f"Unsupported runtime: {runtime}")

                result = {"job_id": job_id, "success": True}
            except Exception as exc:
                result = {
                    "job_id": job_id,
                    "success": False,
                    "error": str(exc),
                    "cancelled": is_cancelled(root, project_root, job_id),
                }

            paths = queue_paths(root, project_root, role)
            write_json_atomic(paths["results"] / f"{job_id}.json", result)
            claim.unlink(missing_ok=True)
            cancellation_path(root, project_root, job_id).unlink(missing_ok=True)
            heartbeat.touch()

            if once:
                return 0
    finally:
        heartbeat.unlink(missing_ok=True)
