from __future__ import annotations

import sys
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from agent_team_lib import core
from agent_team_lib import state_machine


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
    ).stdout.strip()


def init_repo(path: Path) -> str:
    git(path, "init", "-q")
    git(path, "config", "user.email", "test@example.com")
    git(path, "config", "user.name", "Test")
    (path / "README.md").write_text("base\n", encoding="utf-8")
    git(path, "add", "README.md")
    git(path, "commit", "-qm", "init")
    return git(path, "rev-parse", "HEAD")


def status(
    state: str,
    *,
    resume: str = "N/A",
    plan_gate: str = "REQUIRED",
    skip_reason: str = "N/A",
    plan_artifact: str = "N/A",
    plan_approval: str = "NOT_STARTED",
    impl_artifact: str = "N/A",
    code_head: str = "N/A",
    frozen: str = "false",
    review_artifact: str = "N/A",
    review_protocol: str = "NOT_STARTED",
    review_result: str = "NOT_STARTED",
    rw_ids: str = "None",
    acceptance_artifact: str = "N/A",
    accepted_sha: str = "N/A",
) -> str:
    return f"""# Task Status

## Current State

{state}

## Resume State

{resume}

## Workflow

Type: standard
Plan Gate: {plan_gate}
Plan Gate Skip Reason: {skip_reason}

## Current Plan

Version: 1
Artifact: {plan_artifact}
Approval: {plan_approval}

## Current Implementation

Round: 1
Artifact: {impl_artifact}
Previous Head SHA: N/A
Code Head SHA: {code_head}
Review Target Frozen: {frozen}

## Current Review

Round: 1
Artifact: {review_artifact}
Protocol Status: {review_protocol}
Result: {review_result}

## Rework

Round: 1
Active RW IDs: {rw_ids}

## Final Acceptance

Artifact: {acceptance_artifact}
Accepted Code Head SHA: {accepted_sha}
"""


class StateMachineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        self.head = init_repo(self.repo)
        self.task = Path(self.temp.name) / "task"
        for sub in ("plans", "implementations", "reviews"):
            (self.task / sub).mkdir(parents=True)
        (self.task / "TASK.md").write_text("req\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_impl(self, sha: str | None = None) -> None:
        value = sha or self.head
        (self.task / "implementations" / "IMPL-001.md").write_text(
            f"""# Implementation Report

Task Baseline SHA: {self.head}
Previous Head SHA: {self.head}
Code Head SHA: {value}
""",
            encoding="utf-8",
        )

    def write_review(
        self,
        *,
        result: str = "PASS",
        declared: str | None = None,
        observed: str | None = None,
        reviewed_impl: str = "IMPL-001",
        protocol: str = "READY_FOR_REVIEW",
        clean: str = "YES",
    ) -> None:
        declared = declared or self.head
        observed = observed or declared
        (self.task / "reviews" / "REVIEW-001.md").write_text(
            f"""# Review Report

Reviewed Implementation: {reviewed_impl}

## Review Target Verification

Declared Code Head SHA: {declared}
Observed Code Head SHA: {observed}
Unstaged Diff Clean: {clean}
Staged Diff Clean: {clean}
Status Porcelain Clean: {clean}
Control Plane Excluded: {clean}
Protocol Status: {protocol}

## Review Result

{result}
""",
            encoding="utf-8",
        )

    def reviewed_status(self, state: str, *, result: str = "PASS") -> str:
        return status(
            state,
            impl_artifact="IMPL-001.md",
            code_head=self.head,
            frozen="true",
            review_artifact="REVIEW-001.md",
            review_protocol="READY_FOR_REVIEW",
            review_result=result,
        )

    def test_illegal_created_to_accepted_is_rejected(self) -> None:
        with self.assertRaises(core.ProtocolViolation):
            state_machine.validate_transition(
                self.task, status("CREATED"), status("ACCEPTED"), self.head
            )

    def test_fast_path_requires_skip_reason(self) -> None:
        after = status(
            "READY_FOR_IMPLEMENTATION",
            plan_gate="SKIPPED",
            skip_reason="N/A",
        )
        with self.assertRaises(core.ProtocolViolation):
            state_machine.validate_transition(self.task, status("CREATED"), after, self.head)

    def test_impl_cannot_self_approve_plan(self) -> None:
        (self.task / "plans" / "PLAN-v001.md").write_text(
            """# Implementation Plan

## Approval

Approval Status: APPROVED

## Scope

x
""",
            encoding="utf-8",
        )
        after = status(
            "PLAN_REVIEW",
            plan_artifact="PLAN-v001.md",
            plan_approval="PENDING",
        )
        with self.assertRaises(core.ProtocolViolation):
            state_machine.validate_transition(self.task, status("PLANNING"), after, self.head)

    def test_review_pass_gate_accepts_complete_matching_evidence(self) -> None:
        self.write_impl()
        self.write_review()
        before = self.reviewed_status("REVIEWING", result="NOT_STARTED")
        after = self.reviewed_status("READY_FOR_FINAL_ACCEPTANCE")
        state_machine.validate_transition(self.task, before, after, self.head)

    def test_review_pass_gate_rejects_wrong_reviewed_impl(self) -> None:
        self.write_impl()
        self.write_review(reviewed_impl="IMPL-999")
        before = self.reviewed_status("REVIEWING", result="NOT_STARTED")
        after = self.reviewed_status("READY_FOR_FINAL_ACCEPTANCE")
        with self.assertRaises(core.ProtocolViolation):
            state_machine.validate_transition(self.task, before, after, self.head)

    def test_review_pass_gate_rejects_dirty_evidence(self) -> None:
        self.write_impl()
        self.write_review(clean="NO")
        before = self.reviewed_status("REVIEWING", result="NOT_STARTED")
        after = self.reviewed_status("READY_FOR_FINAL_ACCEPTANCE")
        with self.assertRaises(core.ProtocolViolation):
            state_machine.validate_transition(self.task, before, after, self.head)

    def test_ready_for_review_requires_full_exact_sha(self) -> None:
        self.write_impl(self.head[:7])
        before = status("IMPLEMENTING")
        after = status(
            "READY_FOR_REVIEW",
            impl_artifact="IMPL-001.md",
            code_head=self.head[:7],
            frozen="true",
        )
        with self.assertRaises(core.ProtocolViolation):
            state_machine.validate_transition(self.task, before, after, self.head)

    def test_acceptance_requires_matching_review_sha_and_current_head(self) -> None:
        self.write_impl()
        self.write_review()
        (self.task / "ACCEPTANCE.md").write_text(
            f"""# Final Acceptance

Final Result: ACCEPTED
Accepted Review: REVIEW-001.md
Accepted Code Head SHA: {self.head}
""",
            encoding="utf-8",
        )
        before = self.reviewed_status("READY_FOR_FINAL_ACCEPTANCE")
        after = status(
            "ACCEPTED",
            impl_artifact="IMPL-001.md",
            code_head=self.head,
            frozen="true",
            review_artifact="REVIEW-001.md",
            review_protocol="READY_FOR_REVIEW",
            review_result="PASS",
            acceptance_artifact="ACCEPTANCE.md",
            accepted_sha=self.head,
        )
        state_machine.validate_transition(self.task, before, after, self.head)

        (self.repo / "README.md").write_text("outside commit\n", encoding="utf-8")
        git(self.repo, "add", "README.md")
        git(self.repo, "commit", "-qm", "outside")
        changed_head = git(self.repo, "rev-parse", "HEAD")
        with self.assertRaises(core.ProtocolViolation):
            state_machine.validate_transition(self.task, before, after, changed_head)

    def test_entering_blocked_records_resume_state(self) -> None:
        before = status("IMPLEMENTING")
        with self.assertRaises(core.ProtocolViolation):
            state_machine.validate_transition(
                self.task, before, status("BLOCKED", resume="PLANNING"), self.head
            )
        state_machine.validate_transition(
            self.task, before, status("BLOCKED", resume="IMPLEMENTING"), self.head
        )


class ControlBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        init_repo(self.repo)
        self.root = self.repo / ".agent-team"
        core.ensure_control_root(self.repo, self.root)
        (self.root / "INDEX.md").write_text("index\n", encoding="utf-8")
        self.task_a = core.task_root(self.root, self.repo, "TASK-A")
        self.task_b = core.task_root(self.root, self.repo, "TASK-B")
        for task in (self.task_a, self.task_b):
            for sub in ("plans", "implementations", "reviews"):
                (task / sub).mkdir(parents=True, exist_ok=True)
            (task / "TASK.md").write_text("req\n", encoding="utf-8")
            (task / "STATUS.md").write_text("status\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_review_cannot_modify_other_task(self) -> None:
        before = core.project_control_snapshot(self.root, self.repo)
        (self.task_a / "reviews" / "REVIEW-001.md").write_text("review\n", encoding="utf-8")
        (self.task_b / "STATUS.md").write_text("corrupted\n", encoding="utf-8")
        with self.assertRaises(core.ProtocolViolation):
            core.validate_project_control_boundary(
                "Review", self.task_a, before,
                core.project_control_snapshot(self.root, self.repo),
            )

    def test_lead_may_update_index_but_not_other_task(self) -> None:
        before = core.project_control_snapshot(self.root, self.repo)
        (self.root / "INDEX.md").write_text("updated\n", encoding="utf-8")
        after = core.project_control_snapshot(self.root, self.repo)
        core.validate_project_control_boundary("Lead", self.task_a, before, after)

        before = after
        (self.task_b / "TASK.md").write_text("bad\n", encoding="utf-8")
        with self.assertRaises(core.ProtocolViolation):
            core.validate_project_control_boundary(
                "Lead", self.task_a, before,
                core.project_control_snapshot(self.root, self.repo),
            )

    def test_lead_can_change_approval_but_not_plan_content(self) -> None:
        plan = self.task_a / "plans" / "PLAN-v001.md"
        plan.write_text(
            """# Implementation Plan

## Approval

Approval Status: PENDING
Reviewed By: N/A

## Scope

Keep this scope immutable.
""",
            encoding="utf-8",
        )
        before = core.plan_content_snapshot(self.task_a)
        plan.write_text(
            """# Implementation Plan

## Approval

Approval Status: APPROVED
Reviewed By: Lead

## Scope

Keep this scope immutable.
""",
            encoding="utf-8",
        )
        after = core.plan_content_snapshot(self.task_a)
        core.validate_plan_content_boundary("Lead", before, after)

        before = after
        plan.write_text(
            """# Implementation Plan

## Approval

Approval Status: APPROVED
Reviewed By: Lead

## Scope

Changed by Lead.
""",
            encoding="utf-8",
        )
        with self.assertRaises(core.ProtocolViolation):
            core.validate_plan_content_boundary(
                "Lead", before, core.plan_content_snapshot(self.task_a)
            )


if __name__ == "__main__":
    unittest.main()
