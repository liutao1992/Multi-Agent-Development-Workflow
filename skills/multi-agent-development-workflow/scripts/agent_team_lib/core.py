from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import uuid

TERMINAL_STATES = {"ACCEPTED", "CANCELLED", "BLOCKED"}
LEAD_STATES = {
    "CREATED", "PLAN_REVIEW", "READY_FOR_IMPLEMENTATION", "READY_FOR_REVIEW",
    "REWORK", "READY_FOR_FINAL_ACCEPTANCE",
}


class OrchestratorError(RuntimeError):
    pass


class ProtocolViolation(OrchestratorError):
    pass


def sh(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args), cwd=str(cwd), text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check,
    )


def find_project_root(start: Path | None = None) -> Path:
    cwd = (start or Path.cwd()).resolve()
    try:
        result = sh("git", "rev-parse", "--show-toplevel", cwd=cwd)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise OrchestratorError("Current directory is not inside a Git repository.") from exc
    return Path(result.stdout.strip()).resolve()


def git_common_dir(project_root: Path) -> Path:
    value = sh("git", "rev-parse", "--git-common-dir", cwd=project_root).stdout.strip()
    path = Path(value)
    return (project_root / path).resolve() if not path.is_absolute() else path.resolve()


def project_fingerprint(project_root: Path) -> str:
    raw = f"{project_root.resolve()}\n{git_common_dir(project_root)}".encode()
    return hashlib.sha256(raw).hexdigest()[:20]


def control_root(project_root: Path) -> Path:
    configured = os.environ.get("AGENT_TEAM_DIR")
    return Path(configured).expanduser().resolve() if configured else project_root / ".agent-team"


def is_default_control_root(project_root: Path, root: Path) -> bool:
    return root.resolve() == (project_root / ".agent-team").resolve()


def is_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def control_relative_path(project_root: Path, root: Path) -> str | None:
    if not is_within(root, project_root):
        return None
    rel = root.resolve().relative_to(project_root.resolve())
    if str(rel) == ".":
        raise OrchestratorError("Control Root cannot be the Code Plane project root itself.")
    return rel.as_posix()


def git_exclude_path(project_root: Path) -> Path:
    value = sh("git", "rev-parse", "--git-path", "info/exclude", cwd=project_root).stdout.strip()
    path = Path(value)
    return (project_root / path).resolve() if not path.is_absolute() else path.resolve()


def inspect_control_root_safety(project_root: Path, root: Path) -> dict:
    rel = control_relative_path(project_root, root)
    result = {"inside_code_plane": rel is not None, "relative_path": rel, "tracked": False, "ignored": None}
    if rel is None:
        return result
    result["tracked"] = bool(sh("git", "ls-files", "--", rel, cwd=project_root).stdout.strip())
    ignored = subprocess.run(["git", "check-ignore", "-q", "--", rel + "/"], cwd=str(project_root))
    result["ignored"] = ignored.returncode == 0
    return result


def project_control_root(root: Path, project_root: Path) -> Path:
    if is_default_control_root(project_root, root):
        return root
    return root / "projects" / project_fingerprint(project_root)


def tasks_dir(root: Path, project_root: Path) -> Path:
    return project_control_root(root, project_root) / "tasks"


def task_root(root: Path, project_root: Path, task_id: str) -> Path:
    return tasks_dir(root, project_root) / task_id


def project_runtime_root(root: Path, project_root: Path) -> Path:
    return project_control_root(root, project_root) / "runtime"


def task_runtime_dir(root: Path, project_root: Path, task_id: str) -> Path:
    path = project_runtime_root(root, project_root) / "tasks" / task_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_control_root(project_root: Path, root: Path) -> None:
    rel = control_relative_path(project_root, root)
    if rel is not None:
        tracked = sh("git", "ls-files", "--", rel, cwd=project_root).stdout.strip()
        if tracked:
            raise OrchestratorError(
                f"Control Root {root} contains tracked Code Plane files. Remove them from Git tracking first."
            )
        exclude = git_exclude_path(project_root)
        exclude.parent.mkdir(parents=True, exist_ok=True)
        current = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
        entry = rel.rstrip("/") + "/"
        if entry not in {line.strip() for line in current.splitlines()}:
            with exclude.open("a", encoding="utf-8") as fh:
                if current and not current.endswith("\n"):
                    fh.write("\n")
                fh.write(entry + "\n")
    project_control_root(root, project_root).mkdir(parents=True, exist_ok=True)
    tasks_dir(root, project_root).mkdir(parents=True, exist_ok=True)
    project_runtime_root(root, project_root).mkdir(parents=True, exist_ok=True)


def read_status(task: Path) -> str:
    path = task / "STATUS.md"
    if not path.is_file():
        raise OrchestratorError(f"STATUS.md not found: {path}")
    return path.read_text(encoding="utf-8")


def section(status: str, name: str) -> str:
    match = re.search(rf"(?ms)^## {re.escape(name)}\s*\n(.*?)(?=^## |\Z)", status)
    return match.group(1) if match else ""


def section_field(status: str, section_name: str, field: str) -> str:
    match = re.search(rf"(?m)^{re.escape(field)}:\s*(.*?)\s*$", section(status, section_name))
    return match.group(1).strip() if match else "N/A"


def current_state(status: str) -> str:
    for line in section(status, "Current State").splitlines():
        value = line.strip()
        if value:
            return value
    raise OrchestratorError("Unable to resolve Current State from STATUS.md")


def latest_artifact(directory: Path, pattern: str) -> str | None:
    files = sorted(directory.glob(pattern))
    return files[-1].name if files else None


def artifact_pending(task: Path, status: str, kind: str) -> bool:
    mapping = {
        "plan": ("Current Plan", "plans", "PLAN-v*.md"),
        "impl": ("Current Implementation", "implementations", "IMPL-*.md"),
        "review": ("Current Review", "reviews", "REVIEW-*.md"),
    }
    section_name, subdir, pattern = mapping[kind]
    recorded = section_field(status, section_name, "Artifact")
    latest = latest_artifact(task / subdir, pattern)
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


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def control_snapshot(task: Path) -> dict[str, str]:
    if not task.exists():
        return {}
    return {
        p.relative_to(task).as_posix(): hash_file(p)
        for p in sorted(x for x in task.rglob("*") if x.is_file())
    }


def task_digest(task: Path) -> str:
    digest = hashlib.sha256()
    for name, value in sorted(control_snapshot(task).items()):
        digest.update(name.encode())
        digest.update(value.encode())
    return digest.hexdigest()


def git_snapshot(project_root: Path) -> dict[str, str]:
    return {
        "head": sh("git", "rev-parse", "HEAD", cwd=project_root).stdout.strip(),
        "status": sh("git", "status", "--porcelain=v1", "--untracked-files=all", cwd=project_root).stdout,
        "cached": sh("git", "diff", "--cached", "--binary", cwd=project_root).stdout,
        "unstaged": sh("git", "diff", "--binary", cwd=project_root).stdout,
    }


def require_clean_code_plane(project_root: Path) -> None:
    snap = git_snapshot(project_root)
    if snap["status"].strip() or snap["cached"].strip() or snap["unstaged"].strip():
        raise OrchestratorError("Automated orchestration requires a clean Code Plane working tree/index before dispatch.")


def new_files(before: dict[str, str], after: dict[str, str], prefix: str, pattern: re.Pattern[str]) -> list[str]:
    return sorted(
        name for name in after.keys() - before.keys()
        if name.startswith(prefix) and pattern.fullmatch(Path(name).name)
    )


def validate_role_postconditions(
    role: str, state: str, task: Path,
    before_git: dict[str, str], after_git: dict[str, str],
    before_control: dict[str, str], after_control: dict[str, str],
) -> None:
    modified = {n for n in before_control.keys() & after_control.keys() if before_control[n] != after_control[n]}
    removed = before_control.keys() - after_control.keys()
    if removed:
        raise ProtocolViolation(f"{role} removed existing Control Plane artifacts: {sorted(removed)}")

    if role == "Review":
        if before_git != after_git:
            raise ProtocolViolation("Review changed the Code Plane; HEAD/index/worktree must remain unchanged.")
        if {"STATUS.md", "TASK.md"} & modified:
            raise ProtocolViolation("Review modified STATUS.md or TASK.md.")
        forbidden = {p for p in modified if p.startswith(("plans/", "implementations/", "reviews/"))}
        if forbidden:
            raise ProtocolViolation(f"Review modified immutable artifacts: {sorted(forbidden)}")
        created = new_files(before_control, after_control, "reviews/", re.compile(r"REVIEW-\d+\.md"))
        other = (after_control.keys() - before_control.keys()) - set(created)
        if len(created) != 1 or other:
            raise ProtocolViolation(
                f"Review must create exactly one REVIEW artifact; created={created}, other={sorted(other)}"
            )
        return

    if role == "Impl" and state in {"PLANNING", "PLAN_REWORK"}:
        if before_git != after_git:
            raise ProtocolViolation("Planning Impl changed the Code Plane.")
        if {"STATUS.md", "TASK.md"} & modified:
            raise ProtocolViolation("Planning Impl modified STATUS.md or TASK.md.")
        forbidden = {p for p in modified if p.startswith(("plans/", "implementations/", "reviews/"))}
        if forbidden:
            raise ProtocolViolation(f"Planning Impl modified immutable artifacts: {sorted(forbidden)}")
        created = new_files(before_control, after_control, "plans/", re.compile(r"PLAN-v\d+\.md"))
        other = (after_control.keys() - before_control.keys()) - set(created)
        if len(created) != 1 or other:
            raise ProtocolViolation(
                f"Planning Impl must create exactly one PLAN artifact; created={created}, other={sorted(other)}"
            )
        return

    if role == "Impl" and state == "IMPLEMENTING":
        if {"STATUS.md", "TASK.md"} & modified:
            raise ProtocolViolation("Implementation Impl modified STATUS.md or TASK.md.")
        forbidden = {p for p in modified if p.startswith(("plans/", "implementations/", "reviews/"))}
        if forbidden:
            raise ProtocolViolation(f"Implementation Impl modified immutable artifacts: {sorted(forbidden)}")
        created = new_files(before_control, after_control, "implementations/", re.compile(r"IMPL-\d+\.md"))
        other = (after_control.keys() - before_control.keys()) - set(created)
        if len(created) != 1 or other:
            raise ProtocolViolation(
                f"Implementation Impl must create exactly one IMPL artifact; created={created}, other={sorted(other)}"
            )
        if after_git["status"].strip() or after_git["cached"].strip() or after_git["unstaged"].strip():
            raise ProtocolViolation("Implementation Impl did not leave the Code Plane clean after committing.")
        report = (task / created[0]).read_text(encoding="utf-8")
        match = re.search(r"(?m)^Code Head SHA:\s*([0-9a-fA-F]{7,40})\s*$", report)
        if not match or not (
            after_git["head"].startswith(match.group(1)) or match.group(1).startswith(after_git["head"])
        ):
            raise ProtocolViolation("IMPL Code Head SHA does not match observed HEAD.")
        return

    if role == "Lead":
        if before_git != after_git:
            raise ProtocolViolation("Lead changed the Code Plane; Lead may change only Control Plane artifacts.")
        forbidden = {p for p in modified if p.startswith(("implementations/", "reviews/"))}
        if forbidden:
            raise ProtocolViolation(f"Lead modified immutable implementation/review artifacts: {sorted(forbidden)}")
        unexpected = set(after_control.keys() - before_control.keys()) - {"ACCEPTANCE.md"}
        if unexpected:
            raise ProtocolViolation(f"Lead created role-owned or unexpected artifacts: {sorted(unexpected)}")
        return


def write_json_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


class FileLock:
    def __init__(self, path: Path, description: str, recover_stale: bool = True):
        self.path = path
        self.description = description
        self.recover_stale = recover_stale

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            try:
                pid = int(self.path.read_text(encoding="utf-8").strip())
                os.kill(pid, 0)
            except (ValueError, ProcessLookupError):
                if not self.recover_stale:
                    raise OrchestratorError(
                        f"{self.description} has a stale lock. Fail-closed: inspect orphan "
                        f"workers/processes before removing {self.path}."
                    )
                self.path.unlink(missing_ok=True)
                return self.__enter__()
            except PermissionError:
                raise OrchestratorError(f"{self.description} lock exists and owner cannot be inspected.")
            raise OrchestratorError(f"{self.description} is already locked by pid {pid}.")
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return self

    def __exit__(self, exc_type, exc, tb):
        self.path.unlink(missing_ok=True)


def project_lock_path(root: Path, project_root: Path) -> Path:
    return project_runtime_root(root, project_root) / "code-plane.lock"


def task_lock_path(root: Path, project_root: Path, task_id: str) -> Path:
    return task_runtime_dir(root, project_root, task_id) / "orchestrator.lock"
