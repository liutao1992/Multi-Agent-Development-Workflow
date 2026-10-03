from __future__ import annotations

import sys
from pathlib import Path
import subprocess
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from agent_team_lib import processes, queue_runtime


class ProcessInspectionTests(unittest.TestCase):
    def test_failed_or_empty_ps_does_not_prove_quiescence(self) -> None:
        for code, output in ((1, ""), (0, ""), (1, "Z"), (0, "S")):
            with self.subTest(code=code, output=output), \
                 mock.patch.object(queue_runtime, "process_alive", return_value=True), \
                 mock.patch.object(queue_runtime.subprocess, "run", return_value=subprocess.CompletedProcess(["ps"], code, stdout=output)):
                self.assertFalse(queue_runtime.child_process_quiesced(12345))

    def test_denied_ps_exception_does_not_prove_quiescence(self) -> None:
        with mock.patch.object(queue_runtime, "process_alive", return_value=True), \
             mock.patch.object(queue_runtime.subprocess, "run", side_effect=PermissionError):
            self.assertFalse(queue_runtime.child_process_quiesced(12345))

    def test_confirmed_zombie_is_quiesced(self) -> None:
        with mock.patch.object(queue_runtime, "process_alive", return_value=True), \
             mock.patch.object(queue_runtime.subprocess, "run", return_value=subprocess.CompletedProcess(["ps"], 0, stdout="Z+")):
            self.assertTrue(queue_runtime.child_process_quiesced(12345))

    def test_process_exiting_during_inspection_is_quiesced(self) -> None:
        with mock.patch.object(queue_runtime, "process_alive", side_effect=[True, False]), \
             mock.patch.object(queue_runtime.subprocess, "run", return_value=subprocess.CompletedProcess(["ps"], 1, stdout="")):
            self.assertTrue(queue_runtime.child_process_quiesced(12345))

    def test_identity_requires_successful_nonempty_ps_results(self) -> None:
        good_start = subprocess.CompletedProcess(["ps"], 0, stdout="Sat Oct 3 21:00:00 2026")
        good_command = subprocess.CompletedProcess(["ps"], 0, stdout="test-worker")
        for start, command in (
            (subprocess.CompletedProcess(["ps"], 1, stdout=good_start.stdout), good_command),
            (good_start, subprocess.CompletedProcess(["ps"], 1, stdout=good_command.stdout)),
            (good_start, subprocess.CompletedProcess(["ps"], 0, stdout="")),
        ):
            with self.subTest(start=start, command=command), \
                 mock.patch.object(processes, "process_alive", return_value=True), \
                 mock.patch.object(processes.os, "getpgid", return_value=12345), \
                 mock.patch.object(processes.subprocess, "run", side_effect=[start, command]):
                self.assertIsNone(processes.process_identity(12345))


if __name__ == "__main__":
    unittest.main()
