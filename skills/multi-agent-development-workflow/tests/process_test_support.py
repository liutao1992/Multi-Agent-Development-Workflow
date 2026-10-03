from __future__ import annotations

import os
import subprocess
import unittest


def require_process_inspection(test: unittest.TestCase, pid: int) -> None:
    """Probe OS access independently of the production identity implementation."""
    for field in ("lstart", "command", "stat"):
        try:
            result = subprocess.run(
                ["ps", "-o", f"{field}=", "-p", str(pid)],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                check=False,
            )
        except OSError as exc:
            reason = f"Process inspection unavailable: {exc}"
        else:
            if result.returncode == 0 and result.stdout.strip():
                continue
            reason = (
                f"Process inspection unavailable: ps {field} exited {result.returncode}: "
                f"{result.stderr.strip() or 'empty output'}"
            )
        if os.environ.get("AGENT_TEAM_REQUIRE_PROCESS_INSPECTION") == "1":
            test.fail(reason)
        test.skipTest(reason)
