#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from agent_team_lib.core import (
    FileLock, OrchestratorError, ProtocolViolation, TERMINAL_STATES,
    control_root, control_snapshot, current_state, ensure_control_root,
    find_project_root, git_snapshot, inspect_control_root_safety,
    plan_approval_snapshot, plan_content_snapshot, plan_full_snapshot,
    project_control_snapshot, project_fingerprint, project_lock_path,
    project_runtime_root, read_status, require_clean_code_plane, section_field, select_role,
    task_contract_snapshot, task_digest, task_lock_path, task_root, task_runtime_dir, tasks_dir,
    validate_bootstrap_control_boundary, validate_plan_approval_boundary,
    validate_plan_content_boundary, validate_project_control_boundary,
    validate_role_postconditions, validate_task_contract_integrity,
    validate_task_contract_mutation, write_json_atomic,
)
from agent_team_lib.processes import choose_runtime, run_codex, run_pi_rpc
from agent_team_lib.queue_runtime import (
    queue_dispatch, quarantined_jobs, require_no_quarantined_jobs,
    shared_orphan_risk_path, worker_loop,
)
from agent_team_lib.state_machine import validate_terminal_state, validate_transition

ROLE_COMMAND = {"Lead": "Continue", "Impl": "Continue", "Review": "Review"}


def validation_marker(root: Path, project_root: Path, task_id: str) -> Path:
    return task_runtime_dir(root, project_root, task_id) / "pending-validation.json"


def require_no_pending_validation(marker: Path) -> None:
    if marker.exists():
        raise ProtocolViolation(
            f"A previous worker step was not validated. Inspect its artifacts before clearing {marker}."
        )


def log_event(root: Path, project_root: Path, task_id: str, payload: dict) -> None:
    payload = {"at": datetime.now(timezone.utc).isoformat(), **payload}
    with (task_runtime_dir(root, project_root, task_id) / "dispatch.jsonl").open(
        "a", encoding="utf-8"
    ) as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


def build_worker_prompt(role: str, task_id: str, project_root: Path, root: Path) -> str:
    task = task_root(root, project_root, task_id)
    return f"""Use multi-agent-development-workflow.
Role: {role}.
Invocation Mode: Orchestrated Worker.
Project Root: {project_root}
Control Root: {root}
Task Root: {task}
Task: {task_id}
Action: {ROLE_COMMAND[role]}

Execute exactly ONE legal role action and stop at the next handoff boundary.
Read {task / 'STATUS.md'} first and follow exact artifact references.
Impl/Review must not transition STATUS. Lead is the only lifecycle authority.
Do not invoke the orchestrator recursively. Stop rather than inventing a human/product decision.
"""


def build_new_task_prompt(requirement: str, project_root: Path, root: Path) -> str:
    return f"""Use multi-agent-development-workflow.
Role: Lead.
Invocation Mode: Orchestrated Worker.
Project Root: {project_root}
Control Root: {root}

New task requirement:
{requirement}

Create exactly ONE new Task under {tasks_dir(root, project_root)}.
Initialize TASK.md and STATUS.md, freeze Task Baseline SHA, select workflow, and advance only to the next Impl handoff.
Do not modify production code. Do not invoke the orchestrator recursively.
"""


def build_resume_prompt(
    task_id: str,
    project_root: Path,
    root: Path,
    decision: str | None,
) -> str:
    task = task_root(root, project_root, task_id)
    decision_text = decision.strip() if decision else "No new decision text was supplied; use existing Task artifacts."
    return f"""Use multi-agent-development-workflow.
Role: Lead.
Invocation Mode: Orchestrated Worker.
Project Root: {project_root}
Control Root: {root}
Task Root: {task}
Task: {task_id}
Action: Resume BLOCKED task.

Human resolution / decision:
{decision_text}

Read STATUS.md first. The current state MUST be BLOCKED.
Resolve the blocker using the supplied human decision and existing artifacts.
Persist the decision verbatim in STATUS under "## Blocked Resolution" → "Decision:" and record Resolved By / Resolved At.
Transition STATUS exactly to the recorded Resume State, or CANCELLED only if the human decision explicitly cancels the Task.
Do not modify production code.
Do not invoke the orchestrator recursively.
Stop after the lifecycle transition.
"""


def normalize_transport(requested: str) -> str:
    if requested in {"auto", "process", "direct"}:
        return "process"
    if requested == "queue":
        return "queue"
    if requested == "subagent":
        raise OrchestratorError(
            "Native SubAgent transport runs inside the Lead parent session, not this standalone CLI."
        )
    raise OrchestratorError(f"Unknown transport: {requested}")


def dispatch(
    runtime: str, transport: str, role: str, prompt: str,
    project_root: Path, root: Path, task_id: str, timeout: int,
) -> None:
    log_path = task_runtime_dir(root, project_root, task_id) / f"{role.lower()}.log"
    log_event(
        root, project_root, task_id,
        {"event": "dispatch", "runtime": runtime, "transport": transport, "role": role},
    )

    if transport == "queue" and role in {"Impl", "Review"}:
        queue_dispatch(runtime, role, prompt, project_root, root, task_id, timeout)
    elif runtime == "codex":
        run_codex(prompt, project_root, log_path, role, timeout)
    elif runtime == "pi":
        run_pi_rpc(prompt, project_root, log_path, role, timeout)
    else:
        raise OrchestratorError(f"Unsupported runtime: {runtime}")

    log_event(
        root, project_root, task_id,
        {"event": "worker_complete", "runtime": runtime, "transport": transport, "role": role},
    )


def run_task_locked(
    project_root: Path, root: Path, task_id: str, runtime: str,
    transport: str, max_steps: int, timeout: int,
) -> int:
    task = task_root(root, project_root, task_id)
    if not task.is_dir():
        raise OrchestratorError(f"Task not found: {task}")

    with FileLock(task_lock_path(root, project_root, task_id), f"Task {task_id}"):
        marker = validation_marker(root, project_root, task_id)
        require_no_pending_validation(marker)
        for step in range(1, max_steps + 1):
            status = read_status(task)
            state = current_state(status)
            if state in TERMINAL_STATES:
                if state == "ACCEPTED":
                    require_clean_code_plane(project_root)
                validate_terminal_state(task, status, git_snapshot(project_root)["head"])
                print(f"Task {task_id}: {state}")
                return 0 if state in {"ACCEPTED", "CANCELLED"} else 2

            role = select_role(task, status)
            if role is None:
                return 0

            require_clean_code_plane(project_root)
            validate_task_contract_integrity(task, status)
            before_digest = task_digest(task)
            before_git = git_snapshot(project_root)
            before_control = control_snapshot(task)
            before_project_control = project_control_snapshot(root, project_root)
            before_plan_content = plan_content_snapshot(task)
            before_plan_full = plan_full_snapshot(task)
            before_plan_approval = plan_approval_snapshot(task)
            before_task_contract = task_contract_snapshot(task)
            before_status = status

            log_event(
                root, project_root, task_id,
                {"event": "step", "step": step, "state": state, "role": role},
            )
            write_json_atomic(marker, {
                "task_id": task_id, "step": step, "state": state, "role": role,
                "before_digest": before_digest, "before_head": before_git["head"],
            })
            dispatch(
                runtime, transport, role,
                build_worker_prompt(role, task_id, project_root, root),
                project_root, root, task_id, timeout,
            )

            after_git = git_snapshot(project_root)
            after_control = control_snapshot(task)
            after_project_control = project_control_snapshot(root, project_root)
            after_plan_content = plan_content_snapshot(task)
            after_plan_full = plan_full_snapshot(task)
            after_plan_approval = plan_approval_snapshot(task)
            after_task_contract = task_contract_snapshot(task)
            after_status = read_status(task)

            validate_task_contract_mutation(
                role, before_task_contract, after_task_contract, before_status, after_status,
            )
            validate_plan_content_boundary(role, before_plan_content, after_plan_content)
            validate_plan_approval_boundary(
                role, state, before_status, after_status,
                before_plan_full, after_plan_full,
                before_plan_approval, after_plan_approval,
            )
            validate_project_control_boundary(
                role, task, before_project_control, after_project_control,
            )
            validate_role_postconditions(
                role, state, task,
                before_git, after_git, before_control, after_control,
            )
            if role == "Lead":
                validate_transition(task, before_status, after_status, after_git["head"])

            if task_digest(task) == before_digest:
                raise OrchestratorError(
                    f"No protocol progress after {role} worker in state {state}."
                )
            marker.unlink()

        raise OrchestratorError(f"Maximum orchestration steps exceeded ({max_steps}).")


def run_task(
    project_root: Path, root: Path, task_id: str, runtime: str,
    transport: str, max_steps: int, timeout: int,
) -> int:
    with FileLock(
        project_lock_path(root, project_root),
        f"Code Plane {project_root}",
        recover_stale=False,
    ):
        require_no_quarantined_jobs(root, project_root)
        return run_task_locked(
            project_root, root, task_id, runtime, transport, max_steps, timeout
        )


def resume_task(
    project_root: Path,
    root: Path,
    task_id: str,
    decision: str | None,
    runtime: str,
    transport: str,
    max_steps: int,
    timeout: int,
) -> int:
    task = task_root(root, project_root, task_id)
    if not task.is_dir():
        raise OrchestratorError(f"Task not found: {task}")

    with FileLock(
        project_lock_path(root, project_root),
        f"Code Plane {project_root}",
        recover_stale=False,
    ):
        require_no_quarantined_jobs(root, project_root)
        require_clean_code_plane(project_root)

        with FileLock(task_lock_path(root, project_root, task_id), f"Task {task_id}"):
            marker = validation_marker(root, project_root, task_id)
            require_no_pending_validation(marker)
            before_status = read_status(task)
            validate_task_contract_integrity(task, before_status)
            if current_state(before_status) != "BLOCKED":
                raise OrchestratorError(
                    f"resume requires STATUS=BLOCKED; current state is {current_state(before_status)}"
                )

            before_git = git_snapshot(project_root)
            before_control = control_snapshot(task)
            before_project_control = project_control_snapshot(root, project_root)
            before_plan_content = plan_content_snapshot(task)
            before_plan_full = plan_full_snapshot(task)
            before_plan_approval = plan_approval_snapshot(task)
            before_task_contract = task_contract_snapshot(task)

            write_json_atomic(marker, {
                "task_id": task_id, "state": "BLOCKED", "role": "Lead",
                "before_head": before_git["head"],
            })
            dispatch(
                runtime,
                transport,
                "Lead",
                build_resume_prompt(task_id, project_root, root, decision),
                project_root,
                root,
                task_id,
                timeout,
            )

            after_git = git_snapshot(project_root)
            after_control = control_snapshot(task)
            after_project_control = project_control_snapshot(root, project_root)
            after_plan_content = plan_content_snapshot(task)
            after_plan_full = plan_full_snapshot(task)
            after_plan_approval = plan_approval_snapshot(task)
            after_task_contract = task_contract_snapshot(task)
            after_status = read_status(task)

            validate_task_contract_mutation(
                "Lead", before_task_contract, after_task_contract, before_status, after_status,
            )
            validate_plan_content_boundary("Lead", before_plan_content, after_plan_content)
            validate_plan_approval_boundary(
                "Lead", "BLOCKED", before_status, after_status,
                before_plan_full, after_plan_full,
                before_plan_approval, after_plan_approval,
            )
            validate_project_control_boundary(
                "Lead", task, before_project_control, after_project_control,
            )
            validate_role_postconditions(
                "Lead",
                "BLOCKED",
                task,
                before_git,
                after_git,
                before_control,
                after_control,
            )
            validate_transition(task, before_status, after_status, after_git["head"])
            resolution = section_field(after_status, "Blocked Resolution", "Decision")
            if resolution in {"", "N/A"}:
                raise ProtocolViolation("resume must persist the human decision in STATUS Blocked Resolution.")
            if decision and resolution != decision.strip():
                raise ProtocolViolation(
                    "STATUS Blocked Resolution Decision must exactly match the resume CLI decision."
                )
            marker.unlink()

        if current_state(read_status(task)) == "CANCELLED":
            print(f"Task {task_id}: CANCELLED")
            return 0

        return run_task_locked(
            project_root, root, task_id, runtime, transport, max_steps, timeout
        )


def create_task_and_run(
    project_root: Path, root: Path, requirement: str, runtime: str,
    transport: str, max_steps: int, timeout: int,
) -> int:
    with FileLock(
        project_lock_path(root, project_root),
        f"Code Plane {project_root}",
        recover_stale=False,
    ):
        require_no_quarantined_jobs(root, project_root)
        require_clean_code_plane(project_root)
        container = tasks_dir(root, project_root)
        before = {p.name for p in container.iterdir() if p.is_dir()}
        before_project_control = project_control_snapshot(root, project_root)
        bootstrap_log = project_runtime_root(root, project_root) / "bootstrap-lead.log"
        before_git = git_snapshot(project_root)

        prompt = build_new_task_prompt(requirement, project_root, root)
        if runtime == "codex":
            run_codex(prompt, project_root, bootstrap_log, "Lead", timeout)
        elif runtime == "pi":
            run_pi_rpc(prompt, project_root, bootstrap_log, "Lead", timeout)
        else:
            raise OrchestratorError(runtime)

        if git_snapshot(project_root) != before_git:
            raise ProtocolViolation(
                "Lead bootstrap changed Code Plane while creating a Task."
            )

        created = sorted(
            {p.name for p in container.iterdir() if p.is_dir()} - before
        )
        if len(created) != 1:
            raise OrchestratorError(
                f"Expected exactly one new Task, found {len(created)}: {created}"
            )

        after_project_control = project_control_snapshot(root, project_root)
        validate_bootstrap_control_boundary(
            created[0], before_project_control, after_project_control,
        )

        print(f"[orchestrator] created {created[0]}")
        return run_task_locked(
            project_root, root, created[0],
            runtime, transport, max_steps, timeout,
        )


def doctor(project_root: Path, root: Path, requested_runtime: str) -> int:
    safety = inspect_control_root_safety(project_root, root)
    print(f"Project Root: {project_root}")
    print(f"Project Fingerprint: {project_fingerprint(project_root)}")
    print(f"Control Root: {root}")
    print(f"Control Root Exists: {'YES' if root.exists() else 'NO'}")
    print(
        f"Control Root Inside Code Plane: "
        f"{'YES' if safety['inside_code_plane'] else 'NO'}"
    )
    if safety["inside_code_plane"]:
        print(f"Control Root Tracked: {'YES' if safety['tracked'] else 'NO'}")
        print(f"Control Root Ignored: {'YES' if safety['ignored'] else 'NO'}")

    quarantine = quarantined_jobs(root, project_root)
    print(f"Quarantined Queue Jobs: {len(quarantine)}")
    for item in quarantine:
        print(f"  - {item}")
    shared_risk = shared_orphan_risk_path(root, project_root)
    print(f"Shared Orphan Risk: {shared_risk if shared_risk.exists() else 'NO'}")

    for runtime in ("codex", "pi"):
        print(f"Runtime {runtime}: {shutil.which(runtime) or 'NOT FOUND'}")
    if requested_runtime != "auto":
        print(
            f"Requested Runtime: {requested_runtime} "
            f"({shutil.which(requested_runtime) or 'NOT FOUND'})"
        )
    return 0


def command_requires_runtime(command: str) -> bool:
    return command in {"start", "run", "resume", "worker"}


def command_mutates_control_plane(command: str) -> bool:
    return command in {"start", "run", "resume", "worker"}


def main() -> int:
    parser = argparse.ArgumentParser(prog="agent-team")
    parser.add_argument("--project", type=Path)
    parser.add_argument(
        "--runtime",
        choices=["auto", "codex", "pi"],
        default=os.environ.get("AGENT_TEAM_RUNTIME", "auto"),
    )
    parser.add_argument(
        "--transport",
        choices=["auto", "subagent", "process", "direct", "queue"],
        default=os.environ.get("AGENT_TEAM_TRANSPORT", "auto"),
    )
    parser.add_argument("--max-steps", type=int, default=50)
    parser.add_argument("--timeout", type=int, default=3600)

    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor")

    run_p = sub.add_parser("run")
    run_p.add_argument("task_id")

    start_p = sub.add_parser("start")
    start_p.add_argument("requirement")

    status_p = sub.add_parser("status")
    status_p.add_argument("task_id")

    resume_p = sub.add_parser("resume")
    resume_p.add_argument("task_id")
    resume_p.add_argument(
        "decision",
        nargs="?",
        help="Human resolution/decision used to resume the BLOCKED Task.",
    )

    worker_p = sub.add_parser("worker")
    worker_p.add_argument("role", choices=["Impl", "Review"])
    worker_p.add_argument("--once", action="store_true")
    worker_p.add_argument("--poll", type=float, default=0.5)

    args = parser.parse_args()
    project_root = find_project_root(args.project)
    root = control_root(project_root)

    if args.command == "status":
        print(current_state(read_status(task_root(root, project_root, args.task_id))))
        return 0

    if args.command == "doctor":
        return doctor(project_root, root, args.runtime)

    ensure_control_root(project_root, root)
    runtime = choose_runtime(args.runtime)
    transport = normalize_transport(args.transport)

    if args.command == "worker":
        return worker_loop(
            project_root, root, args.role, runtime, args.once, args.poll
        )
    if args.command == "run":
        return run_task(
            project_root, root, args.task_id,
            runtime, transport, args.max_steps, args.timeout,
        )
    if args.command == "resume":
        return resume_task(
            project_root, root, args.task_id, args.decision,
            runtime, transport, args.max_steps, args.timeout,
        )
    if args.command == "start":
        return create_task_and_run(
            project_root, root, args.requirement,
            runtime, transport, args.max_steps, args.timeout,
        )
    raise AssertionError(args.command)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except OrchestratorError as exc:
        print(f"agent-team: {exc}", file=sys.stderr)
        raise SystemExit(1)
