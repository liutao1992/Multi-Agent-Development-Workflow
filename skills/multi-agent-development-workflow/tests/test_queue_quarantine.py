from __future__ import annotations

import sys
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from agent_team_lib import core
from agent_team_lib import queue_runtime


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
    ).stdout


def init_repo(path: Path) -> None:
    git(path, "init", "-q")
    git(path, "config", "user.email", "test@example.com")
    git(path, "config", "user.name", "Test")
    (path / "README.md").write_text("base\n", encoding="utf-8")
    git(path, "add", "README.md")
    git(path, "commit", "-qm", "init")


class QueueQuarantineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        init_repo(self.repo)
        self.root = self.repo / ".agent-team"
        core.ensure_control_root(self.repo, self.root)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_expired_claim_without_child_pid_is_quarantined(self) -> None:
        paths = queue_runtime.queue_paths(self.root, self.repo, "Impl")
        claim = paths["claimed"] / "job-no-pid.json"
        core.write_json_atomic(claim, {
            "job_id": "job-no-pid",
            "state": "CLAIMED",
            "lease_owner": "dead",
            "lease_until": time.time() - 1,
        })

        queue_runtime.recover_expired_claims(self.root, self.repo, "Impl")

        self.assertFalse(claim.exists())
        self.assertFalse((paths["queued"] / "job-no-pid.json").exists())
        self.assertTrue((paths["quarantined"] / "job-no-pid.json").exists())
        with self.assertRaises(core.OrchestratorError):
            queue_runtime.require_no_quarantined_jobs(self.root, self.repo)

    def test_malformed_claim_is_quarantined(self) -> None:
        paths = queue_runtime.queue_paths(self.root, self.repo, "Review")
        claim = paths["claimed"] / "broken.json"
        claim.write_text("{not-json", encoding="utf-8")

        queue_runtime.recover_expired_claims(self.root, self.repo, "Review")

        self.assertFalse(claim.exists())
        self.assertTrue((paths["quarantined"] / "broken.json").exists())

    def test_expired_claim_with_recorded_dead_child_is_requeued(self) -> None:
        paths = queue_runtime.queue_paths(self.root, self.repo, "Impl")
        claim = paths["claimed"] / "safe-retry.json"
        core.write_json_atomic(claim, {
            "job_id": "safe-retry",
            "state": "RUNNING",
            "lease_owner": "dead",
            "lease_until": time.time() - 1,
            "child_pid": 99999999,
        })

        queue_runtime.recover_expired_claims(self.root, self.repo, "Impl")

        self.assertFalse(claim.exists())
        self.assertTrue((paths["queued"] / "safe-retry.json").exists())


if __name__ == "__main__":
    unittest.main()
