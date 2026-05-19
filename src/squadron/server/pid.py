"""PID file management and daemon liveness utilities (stdlib-only)."""

from __future__ import annotations

import errno
import os
from dataclasses import dataclass, field
from pathlib import Path

_DEFAULT_DIR = Path.home() / ".squadron"


@dataclass
class DaemonConfig:
    """Configuration for the daemon process."""

    socket_path: str = field(default_factory=lambda: str(_DEFAULT_DIR / "daemon.sock"))
    port: int = 7862
    pid_path: str = field(default_factory=lambda: str(_DEFAULT_DIR / "daemon.pid"))


def write_pid_file(path: str) -> None:
    """Write the current process PID to a file, creating parents if needed."""
    pid_path = Path(path)
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.write_text(str(os.getpid()))


def remove_pid_file(path: str) -> None:
    """Remove PID file if it exists."""
    pid_path = Path(path)
    if pid_path.exists():
        pid_path.unlink()


def read_pid_file(path: str) -> int | None:
    """Read PID from file. Returns None if file is missing or invalid."""
    pid_path = Path(path)
    if not pid_path.exists():
        return None
    try:
        return int(pid_path.read_text().strip())
    except (ValueError, OSError):
        return None


def is_daemon_running(pid_path: str) -> bool:
    """Check if a daemon process is alive based on its PID file.

    Handles stale PID files: if the process is gone, removes the
    stale file and returns False.
    """
    pid = read_pid_file(pid_path)
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError as exc:
        if exc.errno == errno.ESRCH:
            # Stale PID file — process is gone
            remove_pid_file(pid_path)
            return False
        if exc.errno == errno.EPERM:
            # Process exists but we can't signal it (different user)
            return True
        raise
