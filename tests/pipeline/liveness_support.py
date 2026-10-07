"""Real process fixtures for liveness tests (slice 174): no faked PIDs."""

from __future__ import annotations

import subprocess
import sys


def exited_pid() -> int:
    """The PID of a process that has already exited and been reaped."""
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    return child.pid
