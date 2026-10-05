#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time
import uuid

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from agent_team_lib.core import (
    FileLock, OrchestratorError, ProtocolViolation, TERMINAL_STATES,
    control_root, control_snapshot, current_state, ensure_control_root,
    find_project_root, git_snapshot, inspect_control_root_safety, latest_artifact,
    plan_approval_snapshot, plan_content_snapshot, plan_full_snapshot,
    project_control_snapshot, project_fingerprint, project_lock_path,
    project_runtime_root, read_status, require_clean_code_plane, section_field, select_role,
    task_contract_hash, task_contract_snapshot, task_digest, task_lock_path, task_root,
    task_runtime_dir, tasks_dir,
    validate_bootstrap_control_boundary, validate_plan_approval_boundary,
    validate_plan_content_boundary, validate_project_control_boundary,
    validate_role_postconditions, validate_task_contract_integrity,
    validate_task_contract_mutation, write_json_atomic,
)
from agent_team_lib.processes import choose_runtime, reported_codex_tokens, run_codex, run_pi_rpc
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


def task_metrics(root: Path, project_root: Path, task_id: str) -> dict:
    if not task_root(root, project_root, task_id).is_dir():
        raise OrchestratorError(f"Task not found: {task_id}")
    path = project_runtime_root(root, project_root) / "tasks" / task_id / "dispatch.jsonl"
    summary: dict = {
        "task_id": task_id, "calls": 0, "completed": 0, "failed": 0,
        "validation_failures": 0, "duration_ms": 0, "tokens_used": 0,
        "calls_with_token_usage": 0, "by_role": {},
    }
    if not path.is_file():
        return summary
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        kind = event.get("event")
        if kind == "validation_failed":
            summary["validation_failures"] += 1
            continue
        if kind not in {"worker_complete", "worker_failed", "bootstrap_complete"}:
            continue
        role = event.get("role", "Lead")
        role_summary = summary["by_role"].setdefault(role, {
            "calls": 0, "completed": 0, "failed": 0,
            "duration_ms": 0, "tokens_used": 0, "calls_with_token_usage": 0,
        })
        summary["calls"] += 1
        role_summary["calls"] += 1
        outcome = "failed" if kind == "worker_failed" else "completed"
        summary[outcome] += 1
        role_summary[outcome] += 1
        duration = event.get("duration_ms", 0)
        if isinstance(duration, int) and duration >= 0:
            summary["duration_ms"] += duration
            role_summary["duration_ms"] += duration
        tokens = event.get("tokens_used")
        if isinstance(tokens, int) and tokens >= 0:
            summary["tokens_used"] += tokens
            summary["calls_with_token_usage"] += 1
            role_summary["tokens_used"] += tokens
            role_summary["calls_with_token_usage"] += 1
    return summary


def ensure_task_artifact_dirs(task: Path) -> None:
    task.mkdir(parents=True, exist_ok=True)
    for directory in ("plans", "implementations", "reviews"):
        (task / directory).mkdir(exist_ok=True)


def finalize_bootstrap_contract(task: Path) -> bool:
    """Fill the two derived hash fields after Lead has authored a new contract."""
    task_path = task / "TASK.md"
    task_text = task_path.read_text(encoding="utf-8")
    task_pattern = re.compile(r"(?m)^(Task Contract Hash:[^\S\r\n]*).*$")
    if len(task_pattern.findall(task_text)) != 1:
        raise ProtocolViolation("Bootstrap TASK.md must contain one Task Contract Hash field.")
    computed = task_contract_hash(task_text)
    new_task = task_pattern.sub(lambda match: match.group(1) + computed, task_text)

    status_path = task / "STATUS.md"
    status_text = status_path.read_text(encoding="utf-8")
    section_match = re.search(r"(?m)^## Task Contract[^\S\r\n]*$", status_text)
    if section_match is None:
        raise ProtocolViolation("Bootstrap STATUS.md must contain a Task Contract section.")
    section_end = re.search(r"(?m)^## ", status_text[section_match.end():])
    end = section_match.end() + section_end.start() if section_end else len(status_text)
    body = status_text[section_match.end():end]
    status_pattern = re.compile(r"(?m)^(Hash:[^\S\r\n]*).*$")
    if len(status_pattern.findall(body)) != 1:
        raise ProtocolViolation("Bootstrap STATUS.md Task Contract must contain one Hash field.")
    new_body = status_pattern.sub(lambda match: match.group(1) + computed, body)
    new_status = status_text[:section_match.end()] + new_body + status_text[end:]
    changed = new_task != task_text or new_status != status_text
    if changed:
        task_path.write_text(new_task, encoding="utf-8")
        status_path.write_text(new_status, encoding="utf-8")
    validate_task_contract_integrity(task, new_status)
    return changed


def build_worker_prompt(role: str, task_id: str, project_root: Path, root: Path) -> str:
    task = task_root(root, project_root, task_id)
    skill = SCRIPT_DIR.parent
    status = read_status(task)
    state = current_state(status)
    candidate = None
    if role == "Lead":
        pending = {
            "PLANNING": ("plans", "PLAN-v*.md"),
            "PLAN_REWORK": ("plans", "PLAN-v*.md"),
            "IMPLEMENTING": ("implementations", "IMPL-*.md"),
            "REVIEWING": ("reviews", "REVIEW-*.md"),
        }.get(state)
        if pending:
            name = latest_artifact(task / pending[0], pending[1])
            if name:
                candidate = f"Candidate pending evidence: {pending[0]}/{name}; STATUS Artifact value: {name}. Validate it before recording it."
    elif role == "Review":
        name = section_field(status, "Current Implementation", "Artifact")
        candidate = f"Review exactly STATUS Current Implementation Artifact: {name}."
    role_hint = (
        "Lead: prefer IMPLEMENTING → REVIEWING when the frozen target is valid, and\n"
        "REVIEWING → ACCEPTED after a PASS Review when final acceptance can be decided."
        if role == "Lead" else ""
    )
    if role == "Review":
        schema_hint = f"""Use {skill / 'templates' / 'reviews' / 'REVIEW-001.md'} as the report schema.
The REVIEW artifact MUST contain these exact standalone field labels with verified values:
Declared Code Head SHA:, Observed Code Head SHA:, Unstaged Diff Clean:,
Staged Diff Clean:, Status Porcelain Clean:, Control Plane Excluded:,
Protocol Status:. Put PASS, FAIL, or N/A as the first line under ## Review Result.
Do not replace these fields with prose, a checklist, or renamed headings."""
    elif role == "Lead" and state in {"REVIEWING", "READY_FOR_FINAL_ACCEPTANCE"}:
        schema_hint = f"""If accepting, use {skill / 'templates' / 'ACCEPTANCE.md'}.
The acceptance artifact MUST contain exact standalone fields Final Result: ACCEPTED,
Accepted Review: <current REVIEW filename>, and Accepted Code Head SHA: <full Git SHA>.
Before accepting, verify the REVIEW artifact has every machine-readable target field.
For a PASS review, STATUS Current Review Protocol Status MUST remain READY_FOR_REVIEW
even when Current State becomes ACCEPTED; this field records target verification,
not lifecycle completion. Copy it exactly from the REVIEW artifact.
When consuming a PASS Review, set STATUS Current Review Result to PASS before
transitioning to ACCEPTED; do not leave the previous PENDING value."""
        if state == "REVIEWING":
            schema_hint += """
If Review FAIL requires REVIEWING → REWORK, put confirmed RW-NNN remediation only
under TASK.md ## Rework Requirements. Keep ## Requirement Change Log unchanged;
do not change Task Contract Revision/Hash for Review remediation."""
    else:
        schema_hint = ""
    return f"""Use multi-agent-development-workflow.
Role: {role}.
Invocation Mode: Orchestrated Worker.
Project Root: {project_root}
Control Root: {root}
Task Root: {task}
Task: {task_id}
Action: {ROLE_COMMAND[role]}

Execute exactly ONE legal role action, then return control to the orchestrator.
An intermediate Lead transition also ends this invocation; the validated direct
IMPLEMENTING → REVIEWING and REVIEWING → ACCEPTED routes each count as one action.
Read the entry map near the start of {skill / 'SKILL.md'}, then
{skill / 'roles' / f'{role.lower()}.md'} and {skill / 'automation' / 'worker-brief.md'}.
Use the brief's state-specific evidence list; open other SKILL sections only as needed.
Read {task / 'STATUS.md'} first among Task artifacts and follow exact references.
{candidate or ''}
{role_hint}
{schema_hint}
Impl/Review must not transition STATUS. Lead is the only lifecycle authority.
Do not invoke the orchestrator recursively. Stop rather than inventing a human/product decision.
"""


def build_new_task_prompt(requirement: str, project_root: Path, root: Path) -> str:
    skill = SCRIPT_DIR.parent
    return f"""Use multi-agent-development-workflow.
Role: Lead.
Invocation Mode: Orchestrated Worker.
Project Root: {project_root}
Control Root: {root}
Skill Root: {skill}

New task requirement:
{requirement}

Read the Skill entry map/new-task rules, {skill / 'roles' / 'lead.md'}, and the
TASK.md, STATUS.md, and INDEX.md templates. Do not inspect validator source
unless a documented rule is unclear.
Create exactly ONE new Task under {tasks_dir(root, project_root)}.
Initialize TASK.md and STATUS.md, freeze Task Baseline SHA, select workflow, and advance only to the next Impl handoff.
Write AUTO in both Task Contract Hash fields; the orchestrator computes and fills
the exact hash after bootstrap. Do not spend time calculating it manually.
Do not modify production code. Do not invoke the orchestrator recursively.
After writing TASK.md, STATUS.md, and INDEX.md, stop at the Impl handoff.
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
    if requested == "tmux":
        raise OrchestratorError(
            "tmux-native coordination runs inside the interactive Lead session. "
            "Use scripts/madw start, then talk to Lead."
        )
    if requested == "queue":
        raise OrchestratorError(
            "Queue transport was removed. Use scripts/madw start for tmux-native "
            "coordination, or --transport process for the standalone fallback."
        )
    if requested == "subagent":
        raise OrchestratorError(
            "Native SubAgent transport is not implemented by this standalone CLI."
        )
    raise OrchestratorError(f"Unknown transport: {requested}")


def dispatch(
    runtime: str, transport: str, role: str, prompt: str,
    project_root: Path, root: Path, task_id: str, timeout: int,
) -> None:
    log_path = task_runtime_dir(root, project_root, task_id) / f"{role.lower()}.log"
    log_offset = log_path.stat().st_size if log_path.exists() else 0
    invocation_id = uuid.uuid4().hex
    started = time.monotonic()
    log_event(
        root, project_root, task_id,
        {"event": "dispatch", "invocation_id": invocation_id,
         "runtime": runtime, "transport": transport, "role": role},
    )
    outcome = "worker_failed"
    try:
        if runtime == "codex":
            run_codex(prompt, project_root, log_path, role, timeout)
        elif runtime == "pi":
            run_pi_rpc(prompt, project_root, log_path, role, timeout)
        else:
            raise OrchestratorError(f"Unsupported runtime: {runtime}")
        outcome = "worker_complete"
    finally:
        log_event(root, project_root, task_id, {
            "event": outcome, "invocation_id": invocation_id,
            "runtime": runtime, "transport": transport, "role": role,
            "duration_ms": round((time.monotonic() - started) * 1000),
            "tokens_used": reported_codex_tokens(log_path, log_offset) if runtime == "codex" else None,
        })


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

            try:
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
            except OrchestratorError as exc:
                log_event(root, project_root, task_id, {
                    "event": "validation_failed", "step": step, "state": state,
                    "role": role, "error": str(exc),
                })
                raise
            log_event(root, project_root, task_id, {
                "event": "validation_passed", "step": step, "state": state,
                "next_state": current_state(after_status), "role": role,
            })
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
        require_clean_code_plane(project_root)
        container = tasks_dir(root, project_root)
        before = {p.name for p in container.iterdir() if p.is_dir()}
        before_project_control = project_control_snapshot(root, project_root)
        bootstrap_log = project_runtime_root(root, project_root) / "bootstrap-lead.log"
        before_git = git_snapshot(project_root)

        prompt = build_new_task_prompt(requirement, project_root, root)
        bootstrap_started = time.monotonic()
        bootstrap_offset = bootstrap_log.stat().st_size if bootstrap_log.exists() else 0
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

        task = task_root(root, project_root, created[0])
        hash_corrected = finalize_bootstrap_contract(task)
        ensure_task_artifact_dirs(task)

        log_event(root, project_root, created[0], {
            "event": "bootstrap_complete", "role": "Lead", "runtime": runtime,
            "transport": transport,
            "duration_ms": round((time.monotonic() - bootstrap_started) * 1000),
            "tokens_used": reported_codex_tokens(bootstrap_log, bootstrap_offset) if runtime == "codex" else None,
            "contract_hash_filled": hash_corrected,
        })

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


    for runtime in ("codex", "pi"):
        print(f"Runtime {runtime}: {shutil.which(runtime) or 'NOT FOUND'}")
    if requested_runtime != "auto":
        print(
            f"Requested Runtime: {requested_runtime} "
            f"({shutil.which(requested_runtime) or 'NOT FOUND'})"
        )
    return 0


def command_requires_runtime(command: str) -> bool:
    return command in {"start", "run", "resume"}


def command_mutates_control_plane(command: str) -> bool:
    return command in {"start", "run", "resume"}


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
        choices=["auto", "tmux", "subagent", "process", "direct", "queue"],
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

    metrics_p = sub.add_parser("metrics")
    metrics_p.add_argument("task_id")

    resume_p = sub.add_parser("resume")
    resume_p.add_argument("task_id")
    resume_p.add_argument(
        "decision",
        nargs="?",
        help="Human resolution/decision used to resume the BLOCKED Task.",
    )


    args = parser.parse_args()
    project_root = find_project_root(args.project)
    root = control_root(project_root)

    if args.command == "status":
        print(current_state(read_status(task_root(root, project_root, args.task_id))))
        return 0

    if args.command == "metrics":
        print(json.dumps(task_metrics(root, project_root, args.task_id), ensure_ascii=False, indent=2))
        return 0

    if args.command == "doctor":
        return doctor(project_root, root, args.runtime)

    ensure_control_root(project_root, root)
    runtime = choose_runtime(args.runtime)
    transport = normalize_transport(args.transport)

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
