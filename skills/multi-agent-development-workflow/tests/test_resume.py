from __future__ import annotations

import sys
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import orchestrator as orch
from agent_team_lib import core


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
    ).stdout.strip()


def init_repo(path: Path) -> None:
    git(path, "init", "-q")
    git(path, "config", "user.email", "test@example.com")
    git(path, "config", "user.name", "Test")
    (path / "README.md").write_text("base\n", encoding="utf-8")
    git(path, "add", "README.md")
    git(path, "commit", "-qm", "init")


def make_task() -> tuple[str, str]:
    draft = """# Task
Task Contract Revision: 1
Task Contract Hash: PLACEHOLDER

## Objective
Deliver.

## Requirements
### REQ-001
A.

## Acceptance Criteria
### AC-001
A works.

## Constraints
- None

## Dependencies
- None

## Out of Scope
- None

## Requirement Change Log
None

## Rework Requirements
None
"""
    digest = core.task_contract_hash(draft)
    return draft.replace("PLACEHOLDER", digest), digest


def blocked_status(
    contract_hash: str,
    state: str = "BLOCKED",
    resume: str = "PLANNING",
    decision: str = "N/A",
) -> str:
    return f"""# Task Status

## Current State

{state}

## Resume State

{resume}

## Blocked Resolution

Decision: {decision}
Resolved By: Human via resume
Resolved At: 2026-10-03

## Task Contract

Revision: 1
Hash: {contract_hash}

## Workflow

Type: standard
Plan Gate: REQUIRED
Plan Gate Skip Reason: N/A

## Current Plan

Version: 0
Artifact: N/A
Approval: NOT_STARTED

## Current Implementation

Round: 0
Artifact: N/A
Previous Head SHA: N/A
Code Head SHA: N/A
Review Target Frozen: false

## Current Review

Round: 0
Artifact: N/A
Protocol Status: NOT_STARTED
Result: NOT_STARTED

## Rework

Round: 0
Active RW IDs: None

## Final Acceptance

Artifact: N/A
Accepted Code Head SHA: N/A
"""


class ResumeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        init_repo(self.repo)
        self.root = self.repo / ".agent-team"
        core.ensure_control_root(self.repo, self.root)
        self.task = core.task_root(self.root, self.repo, "TASK-1")
        for sub in ("plans", "implementations", "reviews"):
            (self.task / sub).mkdir(parents=True, exist_ok=True)
        task_text, self.contract_hash = make_task()
        (self.task / "TASK.md").write_text(task_text, encoding="utf-8")
        (self.task / "STATUS.md").write_text(
            blocked_status(self.contract_hash), encoding="utf-8"
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_resume_dispatches_lead_persists_decision_and_continues(self) -> None:
        decision = "Dependency resolved; continue planning."

        def fake_dispatch(*args, **kwargs):
            (self.task / "STATUS.md").write_text(
                blocked_status(
                    self.contract_hash,
                    state="PLANNING",
                    resume="N/A",
                    decision=decision,
                ),
                encoding="utf-8",
            )

        with mock.patch.object(orch, "dispatch", side_effect=fake_dispatch), \
             mock.patch.object(orch, "run_task_locked", return_value=23) as run_next:
            result = orch.resume_task(
                self.repo, self.root, "TASK-1", decision,
                "codex", "process", 50, 60,
            )

        self.assertEqual(result, 23)
        run_next.assert_called_once()
        after = core.read_status(self.task)
        self.assertEqual(core.current_state(after), "PLANNING")
        self.assertEqual(
            core.section_field(after, "Blocked Resolution", "Decision"),
            decision,
        )

    def test_resume_rejects_missing_decision_persistence(self) -> None:
        decision = "Dependency resolved."

        def fake_dispatch(*args, **kwargs):
            (self.task / "STATUS.md").write_text(
                blocked_status(
                    self.contract_hash,
                    state="PLANNING",
                    resume="N/A",
                    decision="N/A",
                ),
                encoding="utf-8",
            )

        with mock.patch.object(orch, "dispatch", side_effect=fake_dispatch), \
             mock.patch.object(orch, "run_task_locked", return_value=23) as run_next:
            with self.assertRaisesRegex(core.ProtocolViolation, "persist the human decision"):
                orch.resume_task(
                    self.repo, self.root, "TASK-1", decision,
                    "codex", "process", 50, 60,
                )

        run_next.assert_not_called()

    def test_resume_rejects_wrong_decision_before_continuing(self) -> None:
        def fake_dispatch(*args, **kwargs):
            (self.task / "STATUS.md").write_text(
                blocked_status(self.contract_hash, state="PLANNING", resume="N/A",
                               decision="Different decision."), encoding="utf-8",
            )

        with mock.patch.object(orch, "dispatch", side_effect=fake_dispatch), \
             mock.patch.object(orch, "run_task_locked", return_value=23) as run_next:
            with self.assertRaisesRegex(core.ProtocolViolation, "exactly match"):
                orch.resume_task(self.repo, self.root, "TASK-1", "Continue planning.",
                                 "codex", "process", 50, 60)
        run_next.assert_not_called()

    def test_resume_without_cli_decision_requires_persisted_decision(self) -> None:
        for value in ("N/A", "", "Use existing approval."):
            with self.subTest(value=value):
                (self.task / "STATUS.md").write_text(blocked_status(self.contract_hash))
                def fake_dispatch(*args, **kwargs):
                    (self.task / "STATUS.md").write_text(
                        blocked_status(self.contract_hash, state="PLANNING", resume="N/A",
                                       decision=value), encoding="utf-8",
                    )
                with mock.patch.object(orch, "dispatch", side_effect=fake_dispatch), \
                     mock.patch.object(orch, "run_task_locked", return_value=23) as run_next:
                    if value in {"N/A", ""}:
                        with self.assertRaisesRegex(core.ProtocolViolation, "persist the human decision"):
                            orch.resume_task(self.repo, self.root, "TASK-1", None,
                                             "codex", "process", 50, 60)
                        run_next.assert_not_called()
                    else:
                        self.assertEqual(orch.resume_task(self.repo, self.root, "TASK-1", None,
                                                         "codex", "process", 50, 60), 23)
                        run_next.assert_called_once()

    def test_resume_requires_blocked_state(self) -> None:
        (self.task / "STATUS.md").write_text(
            blocked_status(
                self.contract_hash, state="PLANNING", resume="N/A"
            ),
            encoding="utf-8",
        )
        with self.assertRaises(core.OrchestratorError):
            orch.resume_task(
                self.repo, self.root, "TASK-1", None,
                "codex", "process", 50, 60,
            )


if __name__ == "__main__":
    unittest.main()
