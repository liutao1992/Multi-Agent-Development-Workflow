from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest import mock

from test_state_machine import make_task_text, status, init_repo, git
import orchestrator as orch
from agent_team_lib import core


class LifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        self.head = init_repo(self.repo)
        self.baseline = self.head
        self.root = self.repo / ".agent-team"
        core.ensure_control_root(self.repo, self.root)
        self.task = core.task_root(self.root, self.repo, "TASK-1")
        for sub in ("plans", "implementations", "reviews"):
            (self.task / sub).mkdir(parents=True, exist_ok=True)
        text, self.digest = make_task_text()
        (self.task / "TASK.md").write_text(text, encoding="utf-8")
        self.fields: dict[str, str] = {}
        self.calls: list[tuple[str, str]] = []
        self.direct_handoffs = False
        self.bold_impl_head = False
        self.wrap_impl_head = False
        self.write_status("CREATED")

    def write_status(self, state: str, **fields: str) -> None:
        self.fields.update(fields)
        (self.task / "STATUS.md").write_text(status(state, self.digest, **self.fields), encoding="utf-8")

    def evidence(self) -> str:
        return f"Task Contract Revision: 1\nTask Contract Hash: {self.digest}\n"

    def write_review(self, round_number: int, result: str) -> None:
        blocking = "### REV-001\nSeverity: BLOCKING\nProblem: Broken A.\nRequired Outcome: Fix A.\n" if result == "FAIL" else "None\n"
        text = (
            self.evidence() + f"Reviewed Implementation: IMPL-{round_number:03d}\n"
            "\n## Review Target Verification\n\n"
            f"Declared Code Head SHA: {self.head}\nObserved Code Head SHA: {self.head}\n"
            "Unstaged Diff Clean: YES\nStaged Diff Clean: YES\nStatus Porcelain Clean: YES\n"
            "Control Plane Excluded: YES\nProtocol Status: READY_FOR_REVIEW\n"
            f"\n## Review Result\n\n{result}\n\n## Blocking Issues\n\n{blocking}"
        )
        (self.task / "reviews" / f"REVIEW-{round_number:03d}.md").write_text(text, encoding="utf-8")

    def dispatch(self, runtime, transport, role, prompt, project, root, task_id, timeout) -> None:
        state = core.current_state(core.read_status(self.task))
        self.calls.append((role, state))
        plan = self.task / "plans" / "PLAN-v001.md"
        if role == "Impl" and state == "PLANNING":
            plan.write_text(self.evidence() + "\n## Scope\nImplement A.\n\n## Approval\nApproval Status: PENDING\n", encoding="utf-8")
        elif role == "Impl" and state == "IMPLEMENTING":
            number = 2 if self.fields.get("rw_ids") == "RW-001" else 1
            previous = self.head
            (self.repo / "README.md").write_text(f"implementation round {number}\n", encoding="utf-8")
            git(self.repo, "add", "README.md")
            git(self.repo, "commit", "-qm", f"implement round {number}")
            self.head = git(self.repo, "rev-parse", "HEAD")
            report = self.evidence() + f"Task Baseline SHA: {self.baseline}\nPrevious Head SHA: {previous}\nCode Head SHA: {self.head}\n"
            if self.wrap_impl_head:
                report = report.replace(f"Code Head SHA: {self.head}", f"Code Head SHA: `{self.head}`")
            if self.bold_impl_head:
                report = report.replace("Code Head SHA:", "- **Code Head SHA:**")
            (self.task / "implementations" / f"IMPL-{number:03d}.md").write_text(report, encoding="utf-8")
        elif role == "Review":
            number = 1 if self.fields["impl_artifact"] == "IMPL-001.md" else 2
            self.write_review(number, "FAIL" if number == 1 else "PASS")
        elif role == "Lead":
            if state == "CREATED":
                self.write_status("PLANNING")
            elif state == "PLANNING":
                self.write_status("PLAN_REVIEW", plan_artifact=plan.name, plan_approval="PENDING")
            elif state == "PLAN_REVIEW":
                plan.write_text(plan.read_text().replace("Approval Status: PENDING", "Approval Status: APPROVED"), encoding="utf-8")
                self.write_status("READY_FOR_IMPLEMENTATION", plan_approval="APPROVED")
            elif state in {"READY_FOR_IMPLEMENTATION", "REWORK"}:
                self.write_status("IMPLEMENTING")
            elif state == "IMPLEMENTING":
                number = 2 if self.fields.get("rw_ids") == "RW-001" else 1
                self.write_status(
                    "REVIEWING" if self.direct_handoffs else "READY_FOR_REVIEW",
                    impl_artifact=f"IMPL-{number:03d}.md", code_head=self.head,
                    frozen="true",
                )
            elif state == "READY_FOR_REVIEW":
                self.write_status("REVIEWING")
            elif state == "REVIEWING" and self.fields["impl_artifact"] == "IMPL-001.md":
                task = self.task / "TASK.md"
                task.write_text(task.read_text().replace("## Rework Requirements\n\nNone", "## Rework Requirements\n\n### RW-001\nRelated Review: REV-001\nFix A."), encoding="utf-8")
                self.write_status("REWORK", review_artifact="REVIEW-001.md", review_protocol="READY_FOR_REVIEW", review_result="FAIL", rw_ids="RW-001")
            elif state == "REVIEWING":
                if self.direct_handoffs:
                    (self.task / "ACCEPTANCE.md").write_text(
                        self.evidence() + f"Final Result: ACCEPTED\nAccepted Review: REVIEW-002.md\nAccepted Code Head SHA: {self.head}\n",
                        encoding="utf-8",
                    )
                self.write_status(
                    "ACCEPTED" if self.direct_handoffs else "READY_FOR_FINAL_ACCEPTANCE",
                    review_artifact="REVIEW-002.md", review_protocol="READY_FOR_REVIEW",
                    review_result="PASS",
                    **({"acceptance_artifact": "ACCEPTANCE.md", "accepted_sha": self.head} if self.direct_handoffs else {}),
                )
            elif state == "READY_FOR_FINAL_ACCEPTANCE":
                (self.task / "ACCEPTANCE.md").write_text(self.evidence() + f"Final Result: ACCEPTED\nAccepted Review: REVIEW-002.md\nAccepted Code Head SHA: {self.head}\n", encoding="utf-8")
                self.write_status("ACCEPTED", acceptance_artifact="ACCEPTANCE.md", accepted_sha=self.head)
            else:
                self.fail(f"Unexpected Lead state {state}")
        else:
            self.fail(f"Unexpected worker {role} in {state}")

    def test_planning_runs_impl_and_lead_without_resume_decision(self) -> None:
        for decision in ("N/A", "Previous human decision."):
            with self.subTest(decision=decision):
                self.calls.clear()
                self.fields.clear()
                (self.task / "plans" / "PLAN-v001.md").unlink(missing_ok=True)
                self.write_status("PLANNING", blocked_decision=decision)
                with mock.patch.object(orch, "dispatch", side_effect=self.dispatch):
                    with self.assertRaisesRegex(core.OrchestratorError, "Maximum orchestration steps"):
                        orch.run_task_locked(self.repo, self.root, "TASK-1", "codex", "process", 2, 60)
                self.assertEqual(self.calls, [("Impl", "PLANNING"), ("Lead", "PLANNING")])
                self.assertEqual(core.current_state(core.read_status(self.task)), "PLAN_REVIEW")

    def test_lead_can_approve_legacy_plan_header_without_changing_content(self) -> None:
        plan = self.task / "plans" / "PLAN-v001.md"
        plan.write_text(
            self.evidence() + "Approval Status: PENDING\n\n## Scope\nImplement A.\n",
            encoding="utf-8",
        )
        self.write_status("PLAN_REVIEW", plan_artifact=plan.name, plan_approval="PENDING")
        before_status = core.read_status(self.task)
        before_content = core.plan_content_snapshot(self.task)
        before_full = core.plan_full_snapshot(self.task)
        before_approval = core.plan_approval_snapshot(self.task)

        plan.write_text(
            plan.read_text(encoding="utf-8").replace(
                "Approval Status: PENDING",
                "Approval Status: APPROVED\n\n## Approval\nDecision: APPROVED",
            ),
            encoding="utf-8",
        )
        self.write_status("READY_FOR_IMPLEMENTATION", plan_approval="APPROVED")
        core.validate_plan_content_boundary("Lead", before_content, core.plan_content_snapshot(self.task))
        core.validate_plan_approval_boundary(
            "Lead", "PLAN_REVIEW", before_status, core.read_status(self.task),
            before_full, core.plan_full_snapshot(self.task),
            before_approval, core.plan_approval_snapshot(self.task),
        )

        plan.write_text(plan.read_text(encoding="utf-8").replace("Implement A.", "Implement B."), encoding="utf-8")
        with self.assertRaisesRegex(core.ProtocolViolation, "immutable Plan content"):
            core.validate_plan_content_boundary("Lead", before_content, core.plan_content_snapshot(self.task))

    def test_full_lifecycle_with_review_fail_rework_and_acceptance(self) -> None:
        with mock.patch.object(orch, "dispatch", side_effect=self.dispatch):
            result = orch.run_task(self.repo, self.root, "TASK-1", "codex", "process", 20, 60)
        self.assertEqual(result, 0)
        self.assertEqual(self.calls, [
            ("Lead", "CREATED"), ("Impl", "PLANNING"), ("Lead", "PLANNING"),
            ("Lead", "PLAN_REVIEW"), ("Lead", "READY_FOR_IMPLEMENTATION"),
            ("Impl", "IMPLEMENTING"), ("Lead", "IMPLEMENTING"),
            ("Lead", "READY_FOR_REVIEW"), ("Review", "REVIEWING"),
            ("Lead", "REVIEWING"), ("Lead", "REWORK"),
            ("Impl", "IMPLEMENTING"), ("Lead", "IMPLEMENTING"),
            ("Lead", "READY_FOR_REVIEW"), ("Review", "REVIEWING"),
            ("Lead", "REVIEWING"), ("Lead", "READY_FOR_FINAL_ACCEPTANCE"),
        ])
        final = core.read_status(self.task)
        self.assertEqual(core.current_state(final), "ACCEPTED")
        self.assertEqual(core.section_field(final, "Blocked Resolution", "Decision"), "N/A")
        self.assertEqual(core.validate_task_contract_integrity(self.task, final), (1, self.digest))
        self.assertNotEqual(self.baseline, self.head)
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")
        self.assertEqual(len(list((self.task / "implementations").glob("IMPL-*.md"))), 2)
        self.assertEqual(len(list((self.task / "reviews").glob("REVIEW-*.md"))), 2)
        self.assertFalse(orch.validation_marker(self.root, self.repo, "TASK-1").exists())
        with mock.patch.object(orch, "dispatch") as dispatch:
            self.assertEqual(
                orch.run_task_locked(self.repo, self.root, "TASK-1", "codex", "process", 1, 60),
                0,
            )
            dispatch.assert_not_called()

    def test_direct_handoffs_reduce_lead_calls_without_skipping_review(self) -> None:
        self.direct_handoffs = True
        self.bold_impl_head = True
        self.wrap_impl_head = True
        with mock.patch.object(orch, "dispatch", side_effect=self.dispatch):
            self.assertEqual(
                orch.run_task(self.repo, self.root, "TASK-1", "codex", "process", 20, 60),
                0,
            )
        self.assertEqual(core.current_state(core.read_status(self.task)), "ACCEPTED")
        self.assertEqual(sum(role == "Review" for role, _ in self.calls), 2)
        self.assertNotIn(("Lead", "READY_FOR_REVIEW"), self.calls)
        self.assertNotIn(("Lead", "READY_FOR_FINAL_ACCEPTANCE"), self.calls)
        self.assertEqual(orch.task_metrics(self.root, self.repo, "TASK-1")["validation_failures"], 0)

    def test_rework_without_valid_review_evidence_is_rejected(self) -> None:
        self.write_status("REVIEWING")
        def invalid_lead(*args, **kwargs):
            path = self.task / "TASK.md"
            path.write_text(path.read_text().replace("## Rework Requirements\n\nNone", "## Rework Requirements\n\n### RW-001\nFix A."), encoding="utf-8")
            self.write_status("REWORK", review_result="FAIL", rw_ids="RW-001")
        with mock.patch.object(orch, "dispatch", side_effect=invalid_lead):
            # No REVIEW exists, so role selection would normally dispatch Review.
            # Select Lead to isolate its attempted unsupported transition.
            with mock.patch.object(orch, "select_role", return_value="Lead"):
                with self.assertRaisesRegex(core.ProtocolViolation, "Required reviews artifact reference is missing"):
                    orch.run_task_locked(self.repo, self.root, "TASK-1", "codex", "process", 1, 60)

    def test_invalid_acceptance_cannot_become_success_on_retry(self) -> None:
        self.write_status("READY_FOR_FINAL_ACCEPTANCE")

        def invalid_lead(*args, **kwargs):
            self.write_status("ACCEPTED")

        with mock.patch.object(orch, "dispatch", side_effect=invalid_lead):
            with self.assertRaises(core.ProtocolViolation):
                orch.run_task_locked(self.repo, self.root, "TASK-1", "codex", "process", 1, 60)

        marker = orch.validation_marker(self.root, self.repo, "TASK-1")
        self.assertTrue(marker.exists())
        with mock.patch.object(orch, "dispatch") as dispatch:
            with self.assertRaisesRegex(core.ProtocolViolation, "previous worker step was not validated"):
                orch.run_task_locked(self.repo, self.root, "TASK-1", "codex", "process", 1, 60)
            dispatch.assert_not_called()

        marker.unlink()
        with self.assertRaises(core.ProtocolViolation):
            orch.run_task_locked(self.repo, self.root, "TASK-1", "codex", "process", 1, 60)

    def test_unfinished_worker_step_blocks_retry(self) -> None:
        with mock.patch.object(orch, "dispatch", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                orch.run_task_locked(self.repo, self.root, "TASK-1", "codex", "process", 1, 60)
        self.assertTrue(orch.validation_marker(self.root, self.repo, "TASK-1").exists())
        with mock.patch.object(orch, "dispatch") as dispatch:
            with self.assertRaises(core.ProtocolViolation):
                orch.run_task_locked(self.repo, self.root, "TASK-1", "codex", "process", 1, 60)
            dispatch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
