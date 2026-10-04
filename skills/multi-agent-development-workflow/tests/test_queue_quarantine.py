from __future__ import annotations

import sys
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from agent_team_lib import core
from agent_team_lib import processes
from agent_team_lib import queue_runtime
from process_test_support import require_process_inspection


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
        self.assertTrue((paths["quarantined"] / "job-no-pid.json").exists())
        other_root = Path(self.temp.name) / "other-control"
        with self.assertRaisesRegex(core.OrchestratorError, "UNKNOWN_ORPHAN_RISK"):
            queue_runtime.require_no_quarantined_jobs(other_root, self.repo)

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

    def test_live_pid_with_mismatched_identity_is_quarantined_not_killed(self) -> None:
        paths = queue_runtime.queue_paths(self.root, self.repo, "Impl")
        child = subprocess.Popen(
            ["python3", "-c", "import time; time.sleep(30)"],
            start_new_session=True,
        )
        try:
            require_process_inspection(self, child.pid)
            identity = processes.process_identity(child.pid)
            self.assertIsNotNone(identity)
            assert identity is not None
            identity["start_time"] = "definitely-not-the-real-start-time"
            claim = paths["claimed"] / "reused-pid.json"
            core.write_json_atomic(claim, {
                "job_id": "reused-pid",
                "state": "RUNNING",
                "lease_owner": "dead",
                "lease_until": time.time() - 1,
                "child_pid": child.pid,
                "child_identity": identity,
            })

            queue_runtime.recover_expired_claims(self.root, self.repo, "Impl")

            self.assertIsNone(child.poll())
            self.assertTrue((paths["quarantined"] / "reused-pid.json").exists())
        finally:
            child.terminate()
            child.wait(timeout=3)

    def test_failed_inspection_quarantines_live_child_without_killing_or_requeueing(self) -> None:
        paths = queue_runtime.queue_paths(self.root, self.repo, "Impl")
        shared_risk = queue_runtime.shared_orphan_risk_path(self.root, self.repo)
        claim = paths["claimed"] / "inspection-denied.json"
        core.write_json_atomic(claim, {
            "job_id": "inspection-denied", "lease_until": time.time() - 1,
            "child_pid": 12345,
            "child_identity": {"pid": 12345, "pgid": 12345, "start_time": "old", "command": "worker"},
        })
        denied = subprocess.CompletedProcess(["ps"], 1, stdout="", stderr="Operation not permitted")
        with mock.patch.object(queue_runtime, "process_alive", return_value=True), \
             mock.patch.object(processes, "process_alive", return_value=True), \
             mock.patch.object(processes.os, "getpgid", return_value=12345), \
             mock.patch.object(processes.subprocess, "run", return_value=denied), \
             mock.patch.object(queue_runtime, "shared_orphan_risk_path", return_value=shared_risk), \
             mock.patch.object(queue_runtime, "terminate_pid_group") as terminate:
            queue_runtime.recover_expired_claims(self.root, self.repo, "Impl")
        terminate.assert_not_called()
        self.assertFalse((paths["queued"] / claim.name).exists())
        self.assertTrue((paths["quarantined"] / claim.name).exists())
        self.assertTrue(queue_runtime.shared_orphan_risk_path(self.root, self.repo).exists())

    def test_cancel_with_failed_inspection_quarantines_live_child(self) -> None:
        paths = queue_runtime.queue_paths(self.root, self.repo, "Impl")
        shared_risk = queue_runtime.shared_orphan_risk_path(self.root, self.repo)
        claim = paths["claimed"] / "cancel-denied.json"
        core.write_json_atomic(claim, {"job_id": "cancel-denied", "child_pid": 12345})
        denied = subprocess.CompletedProcess(["ps"], 1, stdout="", stderr="Operation not permitted")
        with mock.patch.object(queue_runtime, "process_alive", return_value=True), \
             mock.patch.object(queue_runtime.subprocess, "run", return_value=denied), \
             mock.patch.object(queue_runtime, "shared_orphan_risk_path", return_value=shared_risk), \
             mock.patch.object(queue_runtime, "terminate_pid_group") as terminate:
            with self.assertRaisesRegex(core.OrchestratorError, "identity cannot be proven"):
                queue_runtime.cancel_and_quiesce_job(self.root, self.repo, "Impl", "cancel-denied", "timeout")
        terminate.assert_not_called()
        self.assertTrue((paths["quarantined"] / claim.name).exists())


if __name__ == "__main__":
    unittest.main()
