from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "orchestrator.py"
SPEC = importlib.util.spec_from_file_location("agent_team_orchestrator", SCRIPT)
assert SPEC and SPEC.loader
orch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(orch)


def status(state: str, plan: str = "N/A", impl: str = "N/A", review: str = "N/A") -> str:
    return f"""# Task Status

## Current State

{state}

## Current Plan

Artifact: {plan}

## Current Implementation

Artifact: {impl}

## Current Review

Artifact: {review}
"""


class TransportTests(unittest.TestCase):
    def test_auto_and_direct_alias_resolve_to_process(self) -> None:
        self.assertEqual(orch.normalize_transport("auto"), "process")
        self.assertEqual(orch.normalize_transport("process"), "process")
        self.assertEqual(orch.normalize_transport("direct"), "process")

    def test_queue_is_preserved(self) -> None:
        self.assertEqual(orch.normalize_transport("queue"), "queue")

    def test_subagent_fails_closed_in_standalone_cli(self) -> None:
        with self.assertRaises(orch.OrchestratorError):
            orch.normalize_transport("subagent")


class RoleSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.task = Path(self.temp.name)
        for name in ("plans", "implementations", "reviews"):
            (self.task / name).mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_planning_dispatches_impl_until_plan_exists(self) -> None:
        s = status("PLANNING")
        self.assertEqual(orch.select_role(self.task, s), "Impl")
        (self.task / "plans" / "PLAN-v001.md").write_text("plan", encoding="utf-8")
        self.assertEqual(orch.select_role(self.task, s), "Lead")

    def test_implementing_dispatches_lead_after_impl_artifact(self) -> None:
        s = status("IMPLEMENTING", plan="PLAN-v001.md")
        self.assertEqual(orch.select_role(self.task, s), "Impl")
        (self.task / "implementations" / "IMPL-001.md").write_text("impl", encoding="utf-8")
        self.assertEqual(orch.select_role(self.task, s), "Lead")

    def test_reviewing_dispatches_review_then_lead(self) -> None:
        s = status("REVIEWING", plan="PLAN-v001.md", impl="IMPL-001.md")
        self.assertEqual(orch.select_role(self.task, s), "Review")
        (self.task / "reviews" / "REVIEW-001.md").write_text("review", encoding="utf-8")
        self.assertEqual(orch.select_role(self.task, s), "Lead")

    def test_lead_owned_and_terminal_states(self) -> None:
        self.assertEqual(orch.select_role(self.task, status("PLAN_REVIEW")), "Lead")
        self.assertEqual(orch.select_role(self.task, status("READY_FOR_FINAL_ACCEPTANCE")), "Lead")
        self.assertIsNone(orch.select_role(self.task, status("ACCEPTED")))
        self.assertIsNone(orch.select_role(self.task, status("BLOCKED")))


if __name__ == "__main__":
    unittest.main()
