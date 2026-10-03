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


def make_task_text(
    revision: int = 1,
    requirement: str = "Must support A.",
    change_log: str = "None",
) -> tuple[str, str]:
    draft = f"""# Task

Task ID: TASK-1
Task Name: Test
Created: 2026-10-03
Requirement Owner: Lead
Task Contract Revision: {revision}
Task Contract Hash: PLACEHOLDER

## Objective

Deliver the feature.

## Background

Background.

## Requirements

### REQ-001
{requirement}

## Acceptance Criteria

### AC-001
Related Requirements: REQ-001

Expected observable behavior:
A works.

## Constraints

- Keep compatibility.

## Dependencies

- None

## Out of Scope

- B

## Requirement Change Log

{change_log}

## Rework Requirements

None
"""
    digest = core.task_contract_hash(draft)
    return draft.replace("PLACEHOLDER", digest), digest


def status(
    state: str,
    contract_hash: str,
    *,
    contract_revision: int = 1,
    resume: str = "N/A",
    blocked_decision: str = "N/A",
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

## Blocked Resolution

Decision: {blocked_decision}
Resolved By: N/A
Resolved At: N/A

## Task Contract

Revision: {contract_revision}
Hash: {contract_hash}

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
        task_text, self.contract_hash = make_task_text()
        (self.task / "TASK.md").write_text(task_text, encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def st(self, state: str, **kwargs) -> str:
        return status(state, self.contract_hash, **kwargs)

    def write_plan(self, approval: str = "PENDING") -> None:
        (self.task / "plans" / "PLAN-v001.md").write_text(
            f"""# Implementation Plan

Task Contract Revision: 1
Task Contract Hash: {self.contract_hash}

## Approval

Approval Status: {approval}
Reviewed By: N/A
Decision Date: N/A
Decision Notes: N/A

## Scope

Implement A.
""",
            encoding="utf-8",
        )

    def write_impl(self, sha: str | None = None) -> None:
        value = sha or self.head
        (self.task / "implementations" / "IMPL-001.md").write_text(
            f"""# Implementation Report

Task Contract Revision: 1
Task Contract Hash: {self.contract_hash}

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
        blocking: bool = False,
        contract_hash: str | None = None,
    ) -> None:
        declared = declared or self.head
        observed = observed or declared
        blocking_text = (
            """### REV-001
Severity: BLOCKING
Problem: Broken behavior.
Required Outcome: Fix it.
"""
            if blocking else "None"
        )
        (self.task / "reviews" / "REVIEW-001.md").write_text(
            f"""# Review Report

Task Contract Revision: 1
Task Contract Hash: {contract_hash or self.contract_hash}
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

## Blocking Issues

{blocking_text}
""",
            encoding="utf-8",
        )

    def reviewed_status(self, state: str, *, result: str = "PASS", protocol: str = "READY_FOR_REVIEW") -> str:
        return self.st(
            state,
            impl_artifact="IMPL-001.md",
            code_head=self.head,
            frozen="true",
            review_artifact="REVIEW-001.md",
            review_protocol=protocol,
            review_result=result,
        )

    def test_illegal_created_to_accepted_is_rejected(self) -> None:
        with self.assertRaises(core.ProtocolViolation):
            state_machine.validate_transition(
                self.task, self.st("CREATED"), self.st("ACCEPTED"), self.head
            )

    def test_fast_path_requires_skip_reason(self) -> None:
        after = self.st(
            "READY_FOR_IMPLEMENTATION",
            plan_gate="SKIPPED",
            skip_reason="N/A",
        )
        with self.assertRaises(core.ProtocolViolation):
            state_machine.validate_transition(self.task, self.st("CREATED"), after, self.head)

    def test_impl_cannot_self_approve_plan(self) -> None:
        self.write_plan("APPROVED")
        after = self.st(
            "PLAN_REVIEW",
            plan_artifact="PLAN-v001.md",
            plan_approval="PENDING",
        )
        with self.assertRaises(core.ProtocolViolation):
            state_machine.validate_transition(self.task, self.st("PLANNING"), after, self.head)

    def test_review_pass_gate_accepts_complete_matching_evidence(self) -> None:
        self.write_impl()
        self.write_review()
        before = self.reviewed_status("REVIEWING", result="NOT_STARTED")
        after = self.reviewed_status("READY_FOR_FINAL_ACCEPTANCE")
        state_machine.validate_transition(self.task, before, after, self.head)

    def test_review_fail_requires_artifact_fail_and_blocking_issue(self) -> None:
        self.write_impl()
        self.write_review(result="FAIL", blocking=True)
        before = self.reviewed_status("REVIEWING", result="NOT_STARTED")
        after = self.reviewed_status("REWORK", result="FAIL")
        state_machine.validate_transition(self.task, before, after, self.head)

        self.write_review(result="PASS", blocking=True)
        with self.assertRaises(core.ProtocolViolation):
            state_machine.validate_transition(self.task, before, after, self.head)

    def test_review_fail_requires_blocking_rev(self) -> None:
        self.write_impl()
        self.write_review(result="FAIL", blocking=False)
        before = self.reviewed_status("REVIEWING", result="NOT_STARTED")
        after = self.reviewed_status("REWORK", result="FAIL")
        with self.assertRaises(core.ProtocolViolation):
            state_machine.validate_transition(self.task, before, after, self.head)

    def test_review_mismatch_requires_artifact_n_a_and_matching_observed_head(self) -> None:
        self.write_impl()
        self.write_review(
            result="N/A",
            protocol="REVIEW_TARGET_MISMATCH",
            declared=self.head,
            observed=self.head,
            clean="NO",
        )
        before = self.reviewed_status("REVIEWING", result="NOT_STARTED")
        after = self.reviewed_status(
            "READY_FOR_REVIEW",
            result="N/A",
            protocol="REVIEW_TARGET_MISMATCH",
        )
        state_machine.validate_transition(self.task, before, after, self.head)

        self.write_review(
            result="PASS",
            protocol="REVIEW_TARGET_MISMATCH",
            declared=self.head,
            observed=self.head,
            clean="NO",
        )
        with self.assertRaises(core.ProtocolViolation):
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
        before = self.st("IMPLEMENTING")
        after = self.st(
            "READY_FOR_REVIEW",
            impl_artifact="IMPL-001.md",
            code_head=self.head[:7],
            frozen="true",
        )
        with self.assertRaises(core.ProtocolViolation):
            state_machine.validate_transition(self.task, before, after, self.head)

    def test_acceptance_requires_matching_review_contract_sha_and_current_head(self) -> None:
        self.write_impl()
        self.write_review()
        (self.task / "ACCEPTANCE.md").write_text(
            f"""# Final Acceptance

Task Contract Revision: 1
Task Contract Hash: {self.contract_hash}
Final Result: ACCEPTED
Accepted Review: REVIEW-001.md
Accepted Code Head SHA: {self.head}
""",
            encoding="utf-8",
        )
        before = self.reviewed_status("READY_FOR_FINAL_ACCEPTANCE")
        after = self.st(
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

        changed_task, changed_hash = make_task_text(
            revision=2,
            requirement="Must support A and C.",
            change_log=f"""### CHANGE-001
Revision: 2
Previous Hash: {self.contract_hash}
New Hash: PLACEHOLDER
Reason: New requirement.
""",
        )
        changed_task = changed_task.replace("New Hash: PLACEHOLDER", f"New Hash: {changed_hash}")
        (self.task / "TASK.md").write_text(changed_task, encoding="utf-8")
        changed_status = status(
            "ACCEPTED",
            changed_hash,
            contract_revision=2,
            impl_artifact="IMPL-001.md",
            code_head=self.head,
            frozen="true",
            review_artifact="REVIEW-001.md",
            review_protocol="READY_FOR_REVIEW",
            review_result="PASS",
            acceptance_artifact="ACCEPTANCE.md",
            accepted_sha=self.head,
        )
        with self.assertRaises(core.ProtocolViolation):
            state_machine.validate_transition(
                self.task,
                status(
                    "READY_FOR_FINAL_ACCEPTANCE",
                    changed_hash,
                    contract_revision=2,
                    impl_artifact="IMPL-001.md",
                    code_head=self.head,
                    frozen="true",
                    review_artifact="REVIEW-001.md",
                    review_protocol="READY_FOR_REVIEW",
                    review_result="PASS",
                ),
                changed_status,
                self.head,
            )

    def test_entering_blocked_records_resume_state(self) -> None:
        before = self.st("IMPLEMENTING")
        with self.assertRaises(core.ProtocolViolation):
            state_machine.validate_transition(
                self.task, before, self.st("BLOCKED", resume="PLANNING"), self.head
            )
        state_machine.validate_transition(
            self.task, before, self.st("BLOCKED", resume="IMPLEMENTING"), self.head
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
            task_text, _ = make_task_text()
            (task / "TASK.md").write_text(task_text, encoding="utf-8")
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

    def test_plan_approval_is_only_mutable_once_in_plan_review(self) -> None:
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
        before_content = core.plan_content_snapshot(self.task_a)
        before_full = core.plan_full_snapshot(self.task_a)
        before_approval = core.plan_approval_snapshot(self.task_a)

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
        after_content = core.plan_content_snapshot(self.task_a)
        after_full = core.plan_full_snapshot(self.task_a)
        after_approval = core.plan_approval_snapshot(self.task_a)
        core.validate_plan_content_boundary("Lead", before_content, after_content)
        before_status = """## Current Plan\n\nArtifact: PLAN-v001.md\nApproval: PENDING\n"""
        after_status = """## Current Plan\n\nArtifact: PLAN-v001.md\nApproval: APPROVED\n"""
        core.validate_plan_approval_boundary(
            "Lead", "PLAN_REVIEW", before_status, after_status,
            before_full, after_full, before_approval, after_approval,
        )

        frozen_full = after_full
        plan.write_text(
            """# Implementation Plan

## Approval

Approval Status: REWORK
Reviewed By: Lead

## Scope

Keep this scope immutable.
""",
            encoding="utf-8",
        )
        with self.assertRaises(core.ProtocolViolation):
            core.validate_plan_approval_boundary(
                "Lead", "IMPLEMENTING", after_status, after_status,
                frozen_full, core.plan_full_snapshot(self.task_a),
                after_approval, core.plan_approval_snapshot(self.task_a),
            )

    def test_task_contract_change_requires_revision_hash_and_change_log(self) -> None:
        before_task, old_hash = make_task_text()
        (self.task_a / "TASK.md").write_text(before_task, encoding="utf-8")
        before = core.task_contract_snapshot(self.task_a)
        before_status = status("PLAN_REVIEW", old_hash)

        changed, new_hash = make_task_text(
            revision=2,
            requirement="Must support A and C.",
            change_log=f"""### CHANGE-001
Revision: 2
Previous Hash: {old_hash}
New Hash: PLACEHOLDER
Reason: User changed requirement.
""",
        )
        changed = changed.replace("New Hash: PLACEHOLDER", f"New Hash: {new_hash}")
        (self.task_a / "TASK.md").write_text(changed, encoding="utf-8")
        after = core.task_contract_snapshot(self.task_a)
        after_status = status(
            "PLAN_REWORK", new_hash, contract_revision=2
        )
        core.validate_task_contract_mutation(
            "Lead", before, after, before_status, after_status
        )

        broken = changed.replace("Revision: 2", "Revision: 3", 1)
        (self.task_a / "TASK.md").write_text(broken, encoding="utf-8")
        with self.assertRaises(core.ProtocolViolation):
            core.task_contract_snapshot(self.task_a)


if __name__ == "__main__":
    unittest.main()
