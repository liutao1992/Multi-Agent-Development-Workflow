from __future__ import annotations

import os
import sys
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import orchestrator as orch
from agent_team_lib import core
from agent_team_lib import processes
from agent_team_lib import queue_runtime
from process_test_support import require_process_inspection


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout


def init_repo(path: Path) -> None:
    git(path, "init", "-q")
    git(path, "config", "user.email", "test@example.com")
    git(path, "config", "user.name", "Test")
    (path / "README.md").write_text("base\n", encoding="utf-8")
    git(path, "add", "README.md")
    git(path, "commit", "-qm", "init")


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


class RepoTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        init_repo(self.repo)
        self.root = self.repo / ".agent-team"
        core.ensure_control_root(self.repo, self.root)

    def tearDown(self) -> None:
        self.temp.cleanup()


class TransportTests(unittest.TestCase):
    def test_normalize_transport(self) -> None:
        self.assertEqual(orch.normalize_transport("auto"), "process")
        self.assertEqual(orch.normalize_transport("direct"), "process")
        self.assertEqual(orch.normalize_transport("queue"), "queue")
        with self.assertRaises(core.OrchestratorError):
            orch.normalize_transport("subagent")

    def test_command_routing(self) -> None:
        self.assertFalse(orch.command_requires_runtime("status"))
        self.assertFalse(orch.command_requires_runtime("doctor"))
        self.assertTrue(orch.command_requires_runtime("run"))
        self.assertTrue(orch.command_requires_runtime("resume"))
        self.assertFalse(orch.command_mutates_control_plane("status"))
        self.assertTrue(orch.command_mutates_control_plane("worker"))


class RoleSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.task = Path(self.temp.name)
        for name in ("plans", "implementations", "reviews"):
            (self.task / name).mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_selection(self) -> None:
        s = status("PLANNING")
        self.assertEqual(core.select_role(self.task, s), "Impl")
        (self.task / "plans" / "PLAN-v001.md").write_text("plan", encoding="utf-8")
        self.assertEqual(core.select_role(self.task, s), "Lead")

        s2 = status("IMPLEMENTING", plan="PLAN-v001.md")
        self.assertEqual(core.select_role(self.task, s2), "Impl")
        (self.task / "implementations" / "IMPL-001.md").write_text("impl", encoding="utf-8")
        self.assertEqual(core.select_role(self.task, s2), "Lead")

        s3 = status("REVIEWING", plan="PLAN-v001.md", impl="IMPL-001.md")
        self.assertEqual(core.select_role(self.task, s3), "Review")
        (self.task / "reviews" / "REVIEW-001.md").write_text("review", encoding="utf-8")
        self.assertEqual(core.select_role(self.task, s3), "Lead")
        self.assertIsNone(core.select_role(self.task, status("BLOCKED")))


class LockAndNamespaceTests(RepoTestCase):
    def test_project_lock_is_shared_across_control_roots(self) -> None:
        other_root = Path(self.temp.name) / "other-control"
        first = core.project_lock_path(self.root, self.repo)
        second = core.project_lock_path(other_root, self.repo)
        self.assertEqual(first, second)
        self.assertIn(".git", str(first))
        with core.FileLock(first, "code plane", recover_stale=False):
            with self.assertRaises(core.OrchestratorError):
                with core.FileLock(second, "code plane", recover_stale=False):
                    pass

    def test_project_lock_blocks_second_owner(self) -> None:
        path = core.project_lock_path(self.root, self.repo)
        with core.FileLock(path, "code plane"):
            with self.assertRaises(core.OrchestratorError):
                with core.FileLock(path, "code plane"):
                    pass

    def test_stale_project_lock_fails_closed(self) -> None:
        path = core.project_lock_path(self.root, self.repo)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("99999999", encoding="utf-8")
        with self.assertRaises(core.OrchestratorError):
            with core.FileLock(path, "code plane", recover_stale=False):
                pass

    def test_external_control_root_is_project_scoped(self) -> None:
        external = Path(self.temp.name) / "shared-control"
        core.ensure_control_root(self.repo, external)
        task_parent = core.tasks_dir(external, self.repo)
        self.assertIn(core.project_fingerprint(self.repo), str(task_parent))

    def test_custom_control_root_inside_repo_is_ignored(self) -> None:
        custom = self.repo / "control-data"
        core.ensure_control_root(self.repo, custom)
        safety = core.inspect_control_root_safety(self.repo, custom)
        self.assertTrue(safety["inside_code_plane"])
        self.assertFalse(safety["tracked"])
        self.assertTrue(safety["ignored"])

    def test_tracked_custom_control_root_is_rejected(self) -> None:
        custom = self.repo / "tracked-control"
        custom.mkdir()
        (custom / "state.txt").write_text("tracked\n", encoding="utf-8")
        git(self.repo, "add", "tracked-control/state.txt")
        with self.assertRaises(core.OrchestratorError):
            core.ensure_control_root(self.repo, custom)


class QueueTests(RepoTestCase):
    def test_keyboard_interrupt_cancels_queued_job(self) -> None:
        with mock.patch.object(queue_runtime, "worker_available", return_value=True), \
             mock.patch.object(queue_runtime.time, "sleep", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                queue_runtime.queue_dispatch(
                    "codex", "Impl", "work", self.repo, self.root, "TASK-1", 10,
                )
        queued = queue_runtime.queue_paths(self.root, self.repo, "Impl")["queued"]
        self.assertEqual(list(queued.glob("*.json")), [])
        cancelled = list((queue_runtime.queue_root(self.root, self.repo) / "cancelled").glob("*.json"))
        self.assertEqual(len(cancelled), 1)
        self.assertIsNone(queue_runtime.claim_next_job(self.root, self.repo, "Impl", "worker"))

    def test_project_scoped_queue_paths_for_shared_external_root(self) -> None:
        external = Path(self.temp.name) / "shared-control"
        core.ensure_control_root(self.repo, external)
        paths = queue_runtime.queue_paths(external, self.repo, "Impl")
        self.assertIn(core.project_fingerprint(self.repo), str(paths["queued"]))

    def test_expired_claim_without_child_pid_is_quarantined(self) -> None:
        paths = queue_runtime.queue_paths(self.root, self.repo, "Impl")
        claim = paths["claimed"] / "job-1.json"
        core.write_json_atomic(claim, {
            "job_id": "job-1",
            "state": "RUNNING",
            "lease_owner": "dead",
            "lease_until": time.time() - 1,
            "project_root": str(self.repo),
        })
        queue_runtime.recover_expired_claims(self.root, self.repo, "Impl")
        self.assertFalse(claim.exists())
        self.assertFalse((paths["queued"] / "job-1.json").exists())
        self.assertTrue((paths["quarantined"] / "job-1.json").exists())

    def test_cancelled_queued_job_is_not_claimed(self) -> None:
        paths = queue_runtime.queue_paths(self.root, self.repo, "Review")
        core.write_json_atomic(paths["queued"] / "job-2.json", {"job_id": "job-2"})
        queue_runtime.request_cancel(self.root, self.repo, "job-2", "timeout")
        claimed = queue_runtime.claim_next_job(
            self.root, self.repo, "Review", "worker"
        )
        self.assertIsNone(claimed)
        result = core.read_json(paths["results"] / "job-2.json")
        self.assertTrue(result["cancelled"])

    def test_cancel_quiesces_recorded_child_process(self) -> None:
        paths = queue_runtime.queue_paths(self.root, self.repo, "Impl")
        child = subprocess.Popen(
            ["python3", "-c", "import time; time.sleep(30)"],
            start_new_session=True,
        )
        try:
            require_process_inspection(self, child.pid)
            core.write_json_atomic(paths["claimed"] / "job-child.json", {
                "job_id": "job-child",
                "child_pid": child.pid,
                "child_identity": processes.process_identity(child.pid),
                "lease_until": time.time() + 20,
            })
            queue_runtime.cancel_and_quiesce_job(
                self.root,
                self.repo,
                "Impl",
                "job-child",
                "timeout",
                wait_seconds=0.5,
            )
            child.wait(timeout=3)
            self.assertIsNotNone(child.returncode)
        finally:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=3)

    def test_worker_project_mismatch_is_rejected_by_namespace(self) -> None:
        other = Path(self.temp.name) / "other"
        other.mkdir()
        init_repo(other)
        external = Path(self.temp.name) / "shared-control"
        self.assertNotEqual(
            core.project_fingerprint(self.repo),
            core.project_fingerprint(other),
        )
        self.assertNotEqual(
            queue_runtime.queue_root(external, self.repo),
            queue_runtime.queue_root(external, other),
        )


class CleanCodePlaneTests(RepoTestCase):
    def test_dirty_code_plane_is_rejected(self) -> None:
        (self.repo / "README.md").write_text("dirty\n", encoding="utf-8")
        with self.assertRaises(core.OrchestratorError):
            core.require_clean_code_plane(self.repo)


class TimeoutTests(RepoTestCase):
    def test_codex_usage_reads_only_current_invocation(self) -> None:
        log = Path(self.temp.name) / "codex.log"
        log.write_text("tokens used\n1,234\n", encoding="utf-8")
        offset = log.stat().st_size
        log.write_text(log.read_text(encoding="utf-8") + "tokens used\n567\n", encoding="utf-8")
        self.assertEqual(processes.reported_codex_tokens(log, offset), 567)

    def test_pi_reads_settled_event_from_same_write(self) -> None:
        real_popen = subprocess.Popen
        launched: list[str] = []
        script = (
            "import sys,time; sys.stdin.readline(); "
            "sys.stdout.write('{\"type\":\"agent_started\"}\\n{\"type\":\"agent_settled\"}\\n'); "
            "sys.stdout.flush(); time.sleep(3)"
        )
        def fake_pi(command, **kwargs):
            launched.extend(command)
            return real_popen([sys.executable, "-u", "-c", script], **kwargs)

        with mock.patch.dict(os.environ, {
            "AGENT_TEAM_PI_MODEL": "kimi-coding/kimi-for-coding-highspeed",
            "AGENT_TEAM_PI_THINKING": "low",
        }):
            with mock.patch.object(processes.subprocess, "Popen", side_effect=fake_pi):
                processes.run_pi_rpc("work", self.repo, Path(self.temp.name) / "pi.log", "Impl", 2)
        self.assertIn("--no-extensions", launched)
        self.assertIn("--skill", launched)
        self.assertIn("kimi-coding/kimi-for-coding-highspeed", launched)
        self.assertIn("low", launched)

    def test_stream_process_timeout(self) -> None:
        log = Path(self.temp.name) / "timeout.log"
        started = time.monotonic()
        with self.assertRaises(core.OrchestratorError):
            processes.stream_process(
                ["python3", "-c", "import time; time.sleep(30)"],
                self.repo,
                log,
                "Test",
                timeout=1,
            )
        self.assertLess(time.monotonic() - started, 8)

    def test_stream_process_cancel(self) -> None:
        log = Path(self.temp.name) / "cancel.log"
        started = time.monotonic()
        with self.assertRaises(core.OrchestratorError):
            processes.stream_process(
                ["python3", "-c", "import time; time.sleep(30)"],
                self.repo,
                log,
                "Test",
                timeout=30,
                cancelled=lambda: True,
            )
        self.assertLess(time.monotonic() - started, 5)


class DoctorTests(RepoTestCase):
    def test_doctor_does_not_create_external_control_root(self) -> None:
        external = Path(self.temp.name) / "does-not-exist"
        self.assertFalse(external.exists())
        orch.doctor(self.repo, external, "auto")
        self.assertFalse(external.exists())

    def test_dispatch_records_duration_and_codex_usage(self) -> None:
        core.task_root(self.root, self.repo, "TASK-1").mkdir(parents=True)
        def fake_codex(prompt, project, log_path, role, timeout):
            with log_path.open("a", encoding="utf-8") as log:
                log.write("tokens used\n1,234\n")

        with mock.patch.object(orch, "run_codex", side_effect=fake_codex):
            orch.dispatch("codex", "process", "Lead", "work", self.repo, self.root, "TASK-1", 60)
        metrics = orch.task_metrics(self.root, self.repo, "TASK-1")
        self.assertEqual(metrics["calls"], 1)
        self.assertEqual(metrics["completed"], 1)
        self.assertEqual(metrics["tokens_used"], 1234)
        self.assertEqual(metrics["calls_with_token_usage"], 1)
        self.assertGreaterEqual(metrics["duration_ms"], 0)

    def test_prompt_supplies_pending_artifact_basename(self) -> None:
        task = core.task_root(self.root, self.repo, "TASK-1")
        orch.ensure_task_artifact_dirs(task)
        (task / "STATUS.md").write_text(status("IMPLEMENTING"), encoding="utf-8")
        (task / "implementations" / "IMPL-001.md").write_text("evidence\n", encoding="utf-8")
        prompt = orch.build_worker_prompt("Lead", "TASK-1", self.repo, self.root)
        self.assertIn("Candidate pending evidence: implementations/IMPL-001.md", prompt)
        self.assertIn("STATUS Artifact value: IMPL-001.md", prompt)
        self.assertTrue((task / "reviews").is_dir())
        (task / "STATUS.md").write_text(status("REVIEWING", impl="IMPL-001.md"), encoding="utf-8")
        review_prompt = orch.build_worker_prompt("Review", "TASK-1", self.repo, self.root)
        self.assertIn("Declared Code Head SHA:", review_prompt)
        self.assertIn("## Review Result", review_prompt)
        (task / "reviews" / "REVIEW-001.md").write_text("review\n", encoding="utf-8")
        lead_prompt = orch.build_worker_prompt("Lead", "TASK-1", self.repo, self.root)
        self.assertIn("Final Result: ACCEPTED", lead_prompt)
        self.assertIn("Protocol Status MUST remain READY_FOR_REVIEW", lead_prompt)

    def test_bootstrap_fills_derived_contract_hash(self) -> None:
        task = core.task_root(self.root, self.repo, "TASK-1")
        task.mkdir(parents=True)
        (task / "TASK.md").write_text(
            "Task Contract Revision: 1\nTask Contract Hash: AUTO\n"
            "## Objective\n\nCorrect typo.\n\n## Requirements\n\nOnly one word.\n",
            encoding="utf-8",
        )
        (task / "STATUS.md").write_text(
            "## Current State\n\nIMPLEMENTING\n\n## Task Contract\n\n"
            "Revision: 1\nHash: AUTO\n\n## Workflow\n\nType: bugfix\n",
            encoding="utf-8",
        )
        self.assertTrue(orch.finalize_bootstrap_contract(task))
        self.assertFalse(orch.finalize_bootstrap_contract(task))
        core.validate_task_contract_integrity(task, core.read_status(task))


class InvariantTests(RepoTestCase):
    def make_task(self, state: str) -> Path:
        task = core.task_root(self.root, self.repo, "TASK-1")
        for sub in ("plans", "implementations", "reviews"):
            (task / sub).mkdir(parents=True, exist_ok=True)
        (task / "TASK.md").write_text("req\n", encoding="utf-8")
        (task / "STATUS.md").write_text(status(state), encoding="utf-8")
        return task

    def test_review_code_mutation_fails(self) -> None:
        task = self.make_task("REVIEWING")
        before_git = core.git_snapshot(self.repo)
        before_control = core.control_snapshot(task)
        (self.repo / "README.md").write_text("mutated\n", encoding="utf-8")
        (task / "reviews" / "REVIEW-001.md").write_text("review\n", encoding="utf-8")

        with self.assertRaises(core.ProtocolViolation):
            core.validate_role_postconditions(
                "Review",
                "REVIEWING",
                task,
                before_git,
                core.git_snapshot(self.repo),
                before_control,
                core.control_snapshot(task),
            )

    def test_planning_impl_status_mutation_fails(self) -> None:
        task = self.make_task("PLANNING")
        before_git = core.git_snapshot(self.repo)
        before_control = core.control_snapshot(task)
        (task / "STATUS.md").write_text(status("PLAN_REVIEW"), encoding="utf-8")
        (task / "plans" / "PLAN-v001.md").write_text("plan\n", encoding="utf-8")

        with self.assertRaises(core.ProtocolViolation):
            core.validate_role_postconditions(
                "Impl",
                "PLANNING",
                task,
                before_git,
                core.git_snapshot(self.repo),
                before_control,
                core.control_snapshot(task),
            )

    def test_review_exactly_one_review_passes(self) -> None:
        task = self.make_task("REVIEWING")
        before_git = core.git_snapshot(self.repo)
        before_control = core.control_snapshot(task)
        (task / "reviews" / "REVIEW-001.md").write_text("review\n", encoding="utf-8")

        core.validate_role_postconditions(
            "Review",
            "REVIEWING",
            task,
            before_git,
            core.git_snapshot(self.repo),
            before_control,
            core.control_snapshot(task),
        )


if __name__ == "__main__":
    unittest.main()
