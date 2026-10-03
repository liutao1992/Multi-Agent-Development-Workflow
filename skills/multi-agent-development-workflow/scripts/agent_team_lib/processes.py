from __future__ import annotations

import json
import os
from pathlib import Path
import queue as pyqueue
import shutil
import signal
import subprocess
import sys
import threading
import time
from typing import Callable

from .core import OrchestratorError, process_alive

PROCESS_GRACE_SECONDS = 5


def choose_runtime(requested: str) -> str:
    if requested != "auto":
        if not shutil.which(requested):
            raise OrchestratorError(f"Runtime executable not found: {requested}")
        return requested
    for candidate in ("codex", "pi"):
        if shutil.which(candidate):
            return candidate
    raise OrchestratorError("Neither codex nor pi is available.")


def process_identity(pid: int) -> dict[str, object] | None:
    """Return a stable-enough process identity for stale-claim verification."""
    if not process_alive(pid):
        return None
    identity: dict[str, object] = {"pid": pid}
    if os.name == "posix":
        try:
            identity["pgid"] = os.getpgid(pid)
            start = subprocess.run(
                ["ps", "-o", "lstart=", "-p", str(pid)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                check=False,
            ).stdout.strip()
            command = subprocess.run(
                ["ps", "-o", "command=", "-p", str(pid)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                check=False,
            ).stdout.strip()
            if not start:
                return None
            identity["start_time"] = start
            identity["command"] = command
        except (OSError, ProcessLookupError, PermissionError):
            return None
    return identity


def process_identity_matches(expected: dict[str, object] | None) -> bool:
    if not expected or "pid" not in expected:
        return False
    try:
        current = process_identity(int(expected["pid"]))
    except (TypeError, ValueError):
        return False
    if current is None:
        return False
    for key in ("pid", "pgid", "start_time", "command"):
        if key in expected and current.get(key) != expected.get(key):
            return False
    return True


def terminate_pid_group(pid: int, grace: float = 1.0) -> None:
    if not process_alive(pid):
        return
    try:
        if os.name == "posix":
            pgid = os.getpgid(pid)
            os.killpg(pgid, signal.SIGTERM)
        else:
            os.kill(pid, signal.SIGTERM)
        time.sleep(min(grace, 0.25))
        if process_alive(pid):
            if os.name == "posix":
                os.killpg(pgid, signal.SIGKILL)
            else:
                os.kill(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def terminate_process_group(proc: subprocess.Popen, grace: float = PROCESS_GRACE_SECONDS) -> None:
    if proc.poll() is not None:
        return
    try:
        if os.name == "posix":
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        else:
            proc.terminate()
        proc.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        if proc.poll() is None:
            if os.name == "posix":
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            else:
                proc.kill()
        try:
            proc.wait(timeout=grace)
        except Exception:
            pass
    except ProcessLookupError:
        pass


def stream_process(
    command: list[str], cwd: Path, log_path: Path, prefix: str, timeout: int,
    tick: Callable[[subprocess.Popen], None] | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> int:
    lines: pyqueue.Queue[str | None] = pyqueue.Queue()
    with log_path.open("a", encoding="utf-8") as log:
        proc = subprocess.Popen(
            command, cwd=str(cwd), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            bufsize=1, start_new_session=(os.name == "posix"),
        )
        assert proc.stdout is not None

        def reader() -> None:
            try:
                for line in proc.stdout:
                    lines.put(line)
            finally:
                lines.put(None)

        threading.Thread(target=reader, daemon=True).start()
        deadline = time.monotonic() + timeout
        output_closed = False
        try:
            while True:
                if tick:
                    tick(proc)
                if cancelled and cancelled():
                    raise OrchestratorError(f"{prefix} worker was cancelled.")
                if time.monotonic() >= deadline:
                    raise OrchestratorError(f"{prefix} worker exceeded timeout of {timeout} seconds.")
                try:
                    item = lines.get(timeout=0.5)
                    if item is None:
                        output_closed = True
                    else:
                        sys.stdout.write(f"[{prefix}] {item}")
                        sys.stdout.flush()
                        log.write(item)
                        log.flush()
                except pyqueue.Empty:
                    pass
                if proc.poll() is not None and output_closed:
                    return proc.returncode
        except BaseException:
            terminate_process_group(proc)
            raise
        finally:
            proc.stdout.close()


def run_codex(prompt: str, cwd: Path, log_path: Path, role: str, timeout: int, **kwargs) -> None:
    code = stream_process(
        ["codex", "exec", "--full-auto", prompt],
        cwd, log_path, role, timeout, **kwargs,
    )
    if code != 0:
        raise OrchestratorError(f"Codex {role} worker exited with code {code}")


def run_pi_rpc(
    prompt: str, cwd: Path, log_path: Path, role: str, timeout: int,
    tick: Callable[[subprocess.Popen], None] | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> None:
    proc = subprocess.Popen(
        ["pi", "--mode", "rpc", "--no-session", "--approve"],
        cwd=str(cwd),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        start_new_session=(os.name == "posix"),
    )
    assert proc.stdin and proc.stdout and proc.stderr
    proc.stdin.write(json.dumps({"id": "agent-team-prompt", "type": "prompt", "message": prompt}) + "\n")
    proc.stdin.flush()

    events: pyqueue.Queue[tuple[str, str | None]] = pyqueue.Queue()

    def read_stream(stream, name: str) -> None:
        try:
            for line in stream:
                events.put((name, line))
        finally:
            events.put((name, None))

    for stream, name in ((proc.stdout, "stdout"), (proc.stderr, "stderr")):
        threading.Thread(target=read_stream, args=(stream, name), daemon=True).start()
    deadline = time.monotonic() + timeout
    settled = False
    closed: set[str] = set()
    try:
        with log_path.open("a", encoding="utf-8") as log:
            while not settled:
                if tick:
                    tick(proc)
                if cancelled and cancelled():
                    raise OrchestratorError(f"{role} worker was cancelled.")
                if time.monotonic() >= deadline:
                    raise OrchestratorError(f"Pi {role} worker exceeded timeout of {timeout} seconds.")
                try:
                    name, line = events.get(timeout=0.5)
                except pyqueue.Empty:
                    name, line = "", None
                if name and line is None:
                    closed.add(name)
                elif line is not None:
                    log.write(("STDERR " if name == "stderr" else "") + line)
                    log.flush()
                    if name == "stderr":
                        sys.stderr.write(f"[{role}:pi] {line}")
                    else:
                        try:
                            record = json.loads(line)
                        except json.JSONDecodeError:
                            record = {}
                        if record.get("type") == "extension_ui_request":
                            raise OrchestratorError("Pi requested interactive extension UI during unattended orchestration.")
                        if record.get("type") == "agent_settled":
                            settled = True
                if proc.poll() is not None and closed == {"stdout", "stderr"} and events.empty() and not settled:
                    raise OrchestratorError(
                        f"Pi {role} worker exited before agent_settled (code {proc.returncode})."
                    )
    finally:
        terminate_process_group(proc)
        proc.stdin.close()
        proc.stdout.close()
        proc.stderr.close()
