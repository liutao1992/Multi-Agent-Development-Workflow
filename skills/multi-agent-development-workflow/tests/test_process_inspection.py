from __future__ import annotations

import sys
from pathlib import Path
import subprocess
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from agent_team_lib import processes


class ProcessInspectionTests(unittest.TestCase):
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
