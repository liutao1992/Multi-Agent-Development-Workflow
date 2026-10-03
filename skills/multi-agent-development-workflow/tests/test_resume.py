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


def blocked_status(state: str = "BLOCKED", resume: str = "PLANNING") -> str:
    return f"""# Task Status

## Current State

{state}

## Resume State

{resume}

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
        (self.task / "TASK.md").write_text("req\n", encoding="utf-8")
        (self.task / "STATUS.md").write_text(blocked_status(), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_resume_dispatches_lead_and_continues(self) -> None:
        def fake_dispatch(*args, **kwargs):
            (self.task / "STATUS.md").write_text(
                blocked_status(state="PLANNING", resume="N/A"),
                encoding="utf-8",
            )

        with mock.patch.object(orch, "dispatch", side_effect=fake_dispatch), \
             mock.patch.object(orch, "run_task_locked", return_value=23) as run_next:
            result = orch.resume_task(
                self.repo,
                self.root,
                "TASK-1",
                "Dependency resolved; continue planning.",
                "codex",
                "process",
                50,
                60,
            )

        self.assertEqual(result, 23)
        run_next.assert_called_once()
        self.assertEqual(
            core.current_state(core.read_status(self.task)),
            "PLANNING",
        )

    def test_resume_requires_blocked_state(self) -> None:
        (self.task / "STATUS.md").write_text(
            blocked_status(state="PLANNING", resume="N/A"),
            encoding="utf-8",
        )
        with self.assertRaises(core.OrchestratorError):
            orch.resume_task(
                self.repo, self.root, "TASK-1", None,
                "codex", "process", 50, 60,
            )


if __name__ == "__main__":
    unittest.main()
