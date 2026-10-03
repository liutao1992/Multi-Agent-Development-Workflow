#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone

TERMINAL_STATES = {"ACCEPTED", "CANCELLED", "BLOCKED"}

LEAD_STATES = {
    "CREATED",
    "PLAN_REVIEW",
    "READY_FOR_IMPLEMENTATION",
    "READY_FOR_REVIEW",
    "REWORK",
    "READY_FOR_FINAL_ACCEPTANCE",
}

ROLE_COMMAND = {
    "Lead": "Continue",
    "Impl": "Continue",
    "Review": "Review",
}


class OrchestratorError(RuntimeError):
    pass


def sh(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def find_project_root(start: Path | None = None) -> Path:
    cwd = (start or Path.cwd()).resolve()
    try:
        result = sh("git", "rev-parse", "--show-toplevel", cwd=cwd)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise OrchestratorError("Current directory is not inside a Git repository.") from exc
    return Path(result.stdout.strip()).resolve()


def control_root(project_root: Path) -> Path:
    configured = os.environ.get("AGENT_TEAM_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return project_root / ".agent-team"


def git_exclude_path(project_root: Path) -> Path:
    result = sh("git", "rev-parse", "--git-path", "info/exclude", cwd=project_root)
    path = Path(result.stdout.strip())
    if not path.is_absolute():
        path = project_root / path
    return path.resolve()


def ensure_project_control_root(project_root: Path, root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "tasks").mkdir(parents=True, exist_ok=True)
    (root / "runtime").mkdir(parents=True, exist_ok=True)

    if root == project_root / ".agent-team":
        exclude = git_exclude_path(project_root)
        exclude.parent.mkdir(parents=True, exist_ok=True)
        current = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
        lines = {line.strip() for line in current.splitlines()}
        if ".agent-team/" not in lines:
            with exclude.open("a", encoding="utf-8") as fh:
                if current and not current.endswith("\n"):
                    fh.write("\n")
                fh.write(".agent-team/\n")

        tracked = sh("git", "ls-files", ".agent-team", cwd=project_root)
        if tracked.stdout.strip():
            raise OrchestratorError(
                ".agent-team contains tracked files. Move them out of the Code Plane index before auto orchestration."
            )


def task_root(root: Path, task_id: str) -> Path:
    return root / "tasks" / task_id


def read_status(task: Path) -> str:
    path = task / "STATUS.md"
    if not path.is_file():
        raise OrchestratorError(f"STATUS.md not found: {path}")
    return path.read_text(encoding="utf-8")


def section(status: str, name: str) -> str:
    match = re.search(
        rf"(?ms)^## {re.escape(name)}\s*\n(.*?)(?=^## |\Z)",
        status,
    )
    return match.group(1) if match else ""


def section_field(status: str, section_name: str, field: str) -> str:
    body = section(status, section_name)
    match = re.search(rf"(?m)^{re.escape(field)}:\s*(.*?)\s*$", body)
    return match.group(1).strip() if match else "N/A"


def current_state(status: str) -> str:
    body = section(status, "Current State")
    for line in body.splitlines():
        value = line.strip()
        if value:
            return value
    raise OrchestratorError("Unable to resolve Current State from STATUS.md")


def latest_artifact(directory: Path, pattern: str) -> str | None:
    files = sorted(directory.glob(pattern))
    return files[-1].name if files else None


def artifact_pending(task: Path, status: str, kind: str) -> bool:
    if kind == "plan":
        recorded = section_field(status, "Current Plan", "Artifact")
        latest = latest_artifact(task / "plans", "PLAN-v*.md")
    elif kind == "impl":
        recorded = section_field(status, "Current Implementation", "Artifact")
        latest = latest_artifact(task / "implementations", "IMPL-*.md")
    elif kind == "review":
        recorded = section_field(status, "Current Review", "Artifact")
        latest = latest_artifact(task / "reviews", "REVIEW-*.md")
    else:
        raise ValueError(kind)

    return latest is not None and latest != recorded


def select_role(task: Path, status: str) -> str | None:
    state = current_state(status)
    if state in TERMINAL_STATES:
        return None
    if state in {"PLANNING", "PLAN_REWORK"}:
        return "Lead" if artifact_pending(task, status, "plan") else "Impl"
    if state == "IMPLEMENTING":
        return "Lead" if artifact_pending(task, status, "impl") else "Impl"
    if state == "REVIEWING":
        return "Lead" if artifact_pending(task, status, "review") else "Review"
    if state in LEAD_STATES:
        return "Lead"
    raise OrchestratorError(f"Unsupported lifecycle state: {state}")


def snapshot(task: Path) -> str:
    status = read_status(task)
    digest = hashlib.sha256()
    digest.update(status.encode("utf-8"))
    for subdir, pattern in (
        ("plans", "PLAN-v*.md"),
        ("implementations", "IMPL-*.md"),
        ("reviews", "REVIEW-*.md"),
    ):
        path = task / subdir
        for item in sorted(path.glob(pattern)):
            digest.update(item.name.encode("utf-8"))
            digest.update(str(item.stat().st_size).encode("ascii"))
    acceptance = task / "ACCEPTANCE.md"
    if acceptance.exists():
        digest.update(b"ACCEPTANCE.md")
        digest.update(str(acceptance.stat().st_size).encode("ascii"))
    return digest.hexdigest()


def runtime_dir(root: Path, task_id: str) -> Path:
    path = root / "runtime" / task_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_event(root: Path, task_id: str, payload: dict) -> None:
    payload = {
        "at": datetime.now(timezone.utc).isoformat(),
        **payload,
    }
    path = runtime_dir(root, task_id) / "dispatch.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


def build_worker_prompt(role: str, task_id: str, project_root: Path, root: Path) -> str:
    action = ROLE_COMMAND[role]
    return f"""Use multi-agent-development-workflow.
Role: {role}.
Invocation Mode: Orchestrated Worker.

Project Root: {project_root}
Control Root: {root}
Task: {task_id}
Action: {action}

Execute exactly ONE legal action for your role and then stop at the next handoff boundary.

Required behavior:
1. Load SKILL.md and the matching role file.
2. Read {task_root(root, task_id) / 'STATUS.md'} first.
3. Follow exact artifact references from STATUS.md.
4. Do not ask the user to repeat protocol or artifact content that is already available.
5. If you are Impl or Review, do NOT transition lifecycle state and do NOT rewrite STATUS.md; create only the required immutable evidence/artifact for this step.
6. If you are Lead, you are the only worker allowed to update lifecycle state in STATUS.md.
7. Do not start or invoke the orchestrator recursively.
8. If a human decision is genuinely required, do not invent one; leave a concise blocking explanation in your final response without making unrelated changes.
"""


def build_new_task_prompt(requirement: str, project_root: Path, root: Path) -> str:
    return f"""Use multi-agent-development-workflow.
Role: Lead.
Invocation Mode: Orchestrated Worker.

Project Root: {project_root}
Control Root: {root}

New task requirement:
{requirement}

Create exactly ONE new Task namespace under {root / 'tasks'}.
Initialize TASK.md and STATUS.md according to the Skill, establish the project-local Control Plane, freeze Task Baseline SHA, select the workflow, and advance only until the next Impl handoff boundary.

Do not implement production code.
Do not invoke the orchestrator recursively.
"""


def choose_runtime(requested: str) -> str:
    if requested != "auto":
        if not shutil.which(requested):
            raise OrchestratorError(f"Runtime executable not found: {requested}")
        return requested
    if shutil.which("codex"):
        return "codex"
    if shutil.which("pi"):
        return "pi"
    raise OrchestratorError("Neither codex nor pi is available. Pass --runtime explicitly after installing one.")


def stream_process(command: list[str], cwd: Path, log_path: Path, prefix: str) -> int:
    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"\n=== {' '.join(command[:2])} @ {datetime.now(timezone.utc).isoformat()} ===\n")
        proc = subprocess.Popen(
            command,
            cwd=str(cwd),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            sys.stdout.write(f"[{prefix}] {line}")
            sys.stdout.flush()
            log.write(line)
            log.flush()
        return proc.wait()


def run_codex(prompt: str, cwd: Path, log_path: Path, role: str) -> None:
    code = stream_process(
        ["codex", "exec", "--full-auto", prompt],
        cwd,
        log_path,
        role,
    )
    if code != 0:
        raise OrchestratorError(f"Codex {role} worker exited with code {code}")


def run_pi_rpc(prompt: str, cwd: Path, log_path: Path, role: str, timeout: int) -> None:
    proc = subprocess.Popen(
        ["pi", "--mode", "rpc", "--no-session", "--approve"],
        cwd=str(cwd),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    assert proc.stdin is not None
    assert proc.stdout is not None
    assert proc.stderr is not None

    command = {"id": "agent-team-prompt", "type": "prompt", "message": prompt}
    proc.stdin.write(json.dumps(command) + "\n")
    proc.stdin.flush()

    selector = selectors.DefaultSelector()
    selector.register(proc.stdout, selectors.EVENT_READ, "stdout")
    selector.register(proc.stderr, selectors.EVENT_READ, "stderr")
    deadline = time.monotonic() + timeout
    settled = False
    error_seen = None

    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"\n=== pi rpc @ {datetime.now(timezone.utc).isoformat()} ===\n")
        while time.monotonic() < deadline and not settled:
            events = selector.select(timeout=1.0)
            if not events and proc.poll() is not None:
                break
            for key, _ in events:
                line = key.fileobj.readline()
                if not line:
                    continue
                if key.data == "stderr":
                    sys.stderr.write(f"[{role}:pi] {line}")
                    log.write(f"STDERR {line}")
                    continue

                log.write(line)
                log.flush()
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if record.get("type") == "extension_ui_request":
                    error_seen = "Pi worker requested interactive extension UI during unattended orchestration."
                    settled = True
                    break

                if record.get("type") == "agent_settled":
                    settled = True
                    break

        if not settled and error_seen is None:
            error_seen = f"Pi worker did not settle within {timeout} seconds."

    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        proc.kill()

    if error_seen:
        raise OrchestratorError(error_seen)
    if proc.returncode not in (0, -signal.SIGTERM):
        raise OrchestratorError(f"Pi {role} worker exited with code {proc.returncode}")


def workers_dir(root: Path) -> Path:
    path = root / "runtime" / "workers"
    path.mkdir(parents=True, exist_ok=True)
    return path


def heartbeat_path(root: Path, role: str) -> Path:
    return workers_dir(root) / f"{role.lower()}.json"


def process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def worker_available(root: Path, role: str) -> bool:
    path = heartbeat_path(root, role)
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return process_alive(int(data["pid"]))
    except (ValueError, KeyError, json.JSONDecodeError, OSError):
        return False


def queue_dispatch(
    runtime: str,
    role: str,
    prompt: str,
    project_root: Path,
    root: Path,
    task_id: str,
    timeout: int,
) -> None:
    if not worker_available(root, role):
        raise OrchestratorError(
            f"No {role} pane worker is running. Start one with: "
            f"agent-team --runtime {runtime} worker {role}"
        )

    job_id = f"{int(time.time() * 1000)}-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    queue_dir = root / "runtime" / "queue" / role.lower()
    result_dir = root / "runtime" / "results"
    queue_dir.mkdir(parents=True, exist_ok=True)
    result_dir.mkdir(parents=True, exist_ok=True)
    job_path = queue_dir / f"{job_id}.json"
    tmp_path = queue_dir / f".{job_id}.tmp"
    result_path = result_dir / f"{job_id}.json"

    payload = {
        "job_id": job_id,
        "runtime": runtime,
        "role": role,
        "prompt": prompt,
        "project_root": str(project_root),
        "task_id": task_id,
        "timeout": timeout,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp_path, job_path)
    print(f"[orchestrator] queued {role} job {job_id}; waiting for pane worker")

    deadline = time.monotonic() + timeout + 30
    while time.monotonic() < deadline:
        if result_path.exists():
            result = json.loads(result_path.read_text(encoding="utf-8"))
            result_path.unlink(missing_ok=True)
            if result.get("success"):
                return
            raise OrchestratorError(
                f"{role} pane worker failed: {result.get('error', 'unknown error')}"
            )
        if not worker_available(root, role):
            raise OrchestratorError(f"{role} pane worker exited while job {job_id} was pending.")
        time.sleep(0.5)

    raise OrchestratorError(f"Timed out waiting for {role} pane worker job {job_id}.")


def claim_next_job(root: Path, role: str) -> Path | None:
    queue_dir = root / "runtime" / "queue" / role.lower()
    queue_dir.mkdir(parents=True, exist_ok=True)
    for job in sorted(queue_dir.glob("*.json")):
        claimed = job.with_suffix(f".running.{os.getpid()}")
        try:
            os.replace(job, claimed)
            return claimed
        except FileNotFoundError:
            continue
    return None


def worker_loop(
    project_root: Path,
    root: Path,
    role: str,
    default_runtime: str,
    once: bool,
    poll_seconds: float,
) -> int:
    if role == "Lead":
        raise OrchestratorError(
            "Lead is executed directly by the orchestrator in queue transport; "
            "only Impl and Review pane workers are needed."
        )

    heartbeat = heartbeat_path(root, role)
    if worker_available(root, role):
        existing = json.loads(heartbeat.read_text(encoding="utf-8"))
        raise OrchestratorError(f"A {role} pane worker is already running (pid {existing.get('pid')}).")

    heartbeat.write_text(
        json.dumps(
            {
                "pid": os.getpid(),
                "role": role,
                "project_root": str(project_root),
                "started_at": datetime.now(timezone.utc).isoformat(),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(f"[worker:{role}] ready; Control Root={root}")
    print(f"[worker:{role}] waiting for orchestrator jobs")

    try:
        while True:
            job_path = claim_next_job(root, role)
            if job_path is None:
                if once:
                    return 0
                heartbeat.touch()
                time.sleep(poll_seconds)
                continue

            try:
                job = json.loads(job_path.read_text(encoding="utf-8"))
                job_id = job["job_id"]
                runtime = choose_runtime(job.get("runtime", default_runtime))
                prompt = job["prompt"]
                task_id = job["task_id"]
                timeout = int(job.get("timeout", 3600))
                log_path = runtime_dir(root, task_id) / f"{role.lower()}.log"

                print(f"[worker:{role}] starting {job_id} runtime={runtime} task={task_id}")
                if runtime == "codex":
                    run_codex(prompt, project_root, log_path, role)
                elif runtime == "pi":
                    run_pi_rpc(prompt, project_root, log_path, role, timeout)
                else:
                    raise OrchestratorError(f"Unsupported runtime: {runtime}")

                result = {"job_id": job_id, "success": True}
                print(f"[worker:{role}] completed {job_id}")
            except Exception as exc:
                job_id = locals().get("job_id", job_path.name)
                result = {"job_id": job_id, "success": False, "error": str(exc)}
                print(f"[worker:{role}] failed {job_id}: {exc}", file=sys.stderr)

            result_dir = root / "runtime" / "results"
            result_dir.mkdir(parents=True, exist_ok=True)
            target = result_dir / f"{result['job_id']}.json"
            tmp = result_dir / f".{result['job_id']}.tmp"
            tmp.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, target)
            job_path.unlink(missing_ok=True)
            heartbeat.touch()

            if once:
                return 0
    finally:
        heartbeat.unlink(missing_ok=True)


def dispatch(
    runtime: str,
    transport: str,
    role: str,
    prompt: str,
    project_root: Path,
    root: Path,
    task_id: str,
    timeout: int,
) -> None:
    logs = runtime_dir(root, task_id)
    log_path = logs / f"{role.lower()}.log"
    log_event(
        root,
        task_id,
        {"event": "dispatch", "runtime": runtime, "transport": transport, "role": role},
    )

    if transport == "queue" and role in {"Impl", "Review"}:
        queue_dispatch(runtime, role, prompt, project_root, root, task_id, timeout)
    elif transport == "process" and runtime == "codex":
        run_codex(prompt, project_root, log_path, role)
    elif transport == "process" and runtime == "pi":
        run_pi_rpc(prompt, project_root, log_path, role, timeout)
    else:
        raise OrchestratorError(f"Unsupported standalone transport/runtime: {transport}/{runtime}")

    log_event(
        root,
        task_id,
        {"event": "worker_complete", "runtime": runtime, "transport": transport, "role": role},
    )


class TaskLock:
    def __init__(self, path: Path):
        self.path = path
        self.fd: int | None = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            try:
                pid = int(self.path.read_text(encoding="utf-8").strip())
                os.kill(pid, 0)
            except (ValueError, ProcessLookupError):
                self.path.unlink(missing_ok=True)
                self.fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except PermissionError:
                raise OrchestratorError("An orchestrator lock exists and its owner cannot be inspected.")
            else:
                raise OrchestratorError(f"Another orchestrator is already running for this task (pid {pid}).")
        assert self.fd is not None
        os.write(self.fd, str(os.getpid()).encode("ascii"))
        os.close(self.fd)
        self.fd = None
        return self

    def __exit__(self, exc_type, exc, tb):
        self.path.unlink(missing_ok=True)


def run_task(
    project_root: Path,
    root: Path,
    task_id: str,
    runtime: str,
    transport: str,
    max_steps: int,
    timeout: int,
) -> int:
    task = task_root(root, task_id)
    if not task.is_dir():
        raise OrchestratorError(f"Task not found: {task}")

    lock = runtime_dir(root, task_id) / "orchestrator.lock"
    with TaskLock(lock):
        for step in range(1, max_steps + 1):
            status = read_status(task)
            state = current_state(status)
            if state in TERMINAL_STATES:
                print(f"Task {task_id}: {state}")
                return 0 if state in {"ACCEPTED", "CANCELLED"} else 2

            role = select_role(task, status)
            if role is None:
                return 0

            before = snapshot(task)
            print(f"[orchestrator] step={step} state={state} role={role}")
            log_event(
                root,
                task_id,
                {"event": "step", "step": step, "state": state, "role": role},
            )
            prompt = build_worker_prompt(role, task_id, project_root, root)
            dispatch(runtime, transport, role, prompt, project_root, root, task_id, timeout)
            after = snapshot(task)

            if after == before:
                log_event(
                    root,
                    task_id,
                    {
                        "event": "stopped_no_progress",
                        "step": step,
                        "state": state,
                        "role": role,
                    },
                )
                raise OrchestratorError(
                    f"No protocol progress after {role} worker in state {state}. "
                    "Stopping rather than retrying blindly; inspect the role log for a human decision or runtime failure."
                )

        raise OrchestratorError(f"Maximum orchestration steps exceeded ({max_steps}).")


def create_task_and_run(
    project_root: Path,
    root: Path,
    requirement: str,
    runtime: str,
    transport: str,
    max_steps: int,
    timeout: int,
) -> int:
    tasks_dir = root / "tasks"
    before = {p.name for p in tasks_dir.iterdir() if p.is_dir()}
    bootstrap_log = root / "runtime" / "bootstrap-lead.log"
    prompt = build_new_task_prompt(requirement, project_root, root)

    if runtime == "codex":
        run_codex(prompt, project_root, bootstrap_log, "Lead")
    elif runtime == "pi":
        run_pi_rpc(prompt, project_root, bootstrap_log, "Lead", timeout)
    else:
        raise OrchestratorError(runtime)

    after = {p.name for p in tasks_dir.iterdir() if p.is_dir()}
    created = sorted(after - before)
    if len(created) != 1:
        raise OrchestratorError(
            f"Expected exactly one new Task, found {len(created)}: {created}. "
            f"Inspect {bootstrap_log}."
        )
    task_id = created[0]
    print(f"[orchestrator] created {task_id}")
    return run_task(project_root, root, task_id, runtime, transport, max_steps, timeout)


def doctor(project_root: Path, root: Path, runtime: str) -> int:
    print(f"Project Root: {project_root}")
    print(f"Control Root: {root}")
    print(f"Runtime: {runtime}")
    print(f"Runtime Path: {shutil.which(runtime)}")
    if root == project_root / ".agent-team":
        tracked = sh("git", "ls-files", ".agent-team", cwd=project_root)
        print(f"Control Plane tracked: {'YES' if tracked.stdout.strip() else 'NO'}")
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", ".agent-team/"],
            cwd=str(project_root),
        )
        print(f"Control Plane ignored: {'YES' if ignored.returncode == 0 else 'NO'}")
    return 0


def normalize_transport(requested: str) -> str:
    """Resolve standalone CLI transport.

    Native SubAgent orchestration belongs to the already-running parent agent
    session and cannot be attached to from this standalone process.
    """
    if requested in {"auto", "process", "direct"}:
        return "process"
    if requested == "queue":
        return "queue"
    if requested == "subagent":
        raise OrchestratorError(
            "Native SubAgent transport must be run inside the Lead parent agent session. "
            "The standalone agent-team CLI supports process or queue fallback transports."
        )
    raise OrchestratorError(f"Unknown transport: {requested}")


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="agent-team",
        description="Automatic Lead/Impl/Review orchestrator for multi-agent-development-workflow.",
    )
    parser.add_argument("--project", type=Path, help="Path inside the target Git repository.")
    parser.add_argument("--runtime", choices=["auto", "codex", "pi"], default=os.environ.get("AGENT_TEAM_RUNTIME", "auto"))
    parser.add_argument(
        "--transport",
        choices=["auto", "subagent", "process", "direct", "queue"],
        default=os.environ.get("AGENT_TEAM_TRANSPORT", "auto"),
        help=(
            "Standalone transport. auto/process launch worker processes; queue delegates "
            "Impl/Review to Warp pane workers. subagent is reserved for native parent-session "
            "orchestration and will fail closed in this standalone CLI."
        ),
    )
    parser.add_argument("--max-steps", type=int, default=50)
    parser.add_argument("--timeout", type=int, default=3600, help="Per-worker timeout in seconds.")

    sub = parser.add_subparsers(dest="command", required=True)
    run_p = sub.add_parser("run", help="Continue an existing Task automatically until terminal/block.")
    run_p.add_argument("task_id")

    start_p = sub.add_parser("start", help="Create one Task from a requirement and run it automatically.")
    start_p.add_argument("requirement")

    status_p = sub.add_parser("status", help="Print the current lifecycle state.")
    status_p.add_argument("task_id")

    worker_p = sub.add_parser("worker", help="Run a Warp pane worker that consumes orchestrator jobs.")
    worker_p.add_argument("role", choices=["Impl", "Review"])
    worker_p.add_argument("--once", action="store_true", help="Exit after one job, or immediately if none is queued.")
    worker_p.add_argument("--poll", type=float, default=0.5, help="Queue polling interval in seconds.")

    sub.add_parser("doctor", help="Validate local orchestration prerequisites.")

    args = parser.parse_args()
    project_root = find_project_root(args.project)
    root = control_root(project_root)
    ensure_project_control_root(project_root, root)
    runtime = choose_runtime(args.runtime)
    transport = normalize_transport(args.transport)

    if args.command == "doctor":
        return doctor(project_root, root, runtime)
    if args.command == "worker":
        return worker_loop(project_root, root, args.role, runtime, args.once, args.poll)
    if args.command == "status":
        status = read_status(task_root(root, args.task_id))
        print(current_state(status))
        return 0
    if args.command == "run":
        return run_task(project_root, root, args.task_id, runtime, transport, args.max_steps, args.timeout)
    if args.command == "start":
        return create_task_and_run(
            project_root,
            root,
            args.requirement,
            runtime,
            transport,
            args.max_steps,
            args.timeout,
        )
    raise AssertionError(args.command)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except OrchestratorError as exc:
        print(f"agent-team: {exc}", file=sys.stderr)
        raise SystemExit(1)
