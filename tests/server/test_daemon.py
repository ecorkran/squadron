"""Tests for daemon PID file management and lifecycle utilities."""

from __future__ import annotations

import os
from pathlib import Path

from squadron.server.pid import (
    is_daemon_running,
    read_pid_file,
    remove_pid_file,
    write_pid_file,
)


def test_write_and_read_pid_file(tmp_path: Path):
    """Write PID, read back, matches os.getpid()."""
    pid_file = str(tmp_path / "daemon.pid")
    write_pid_file(pid_file)
    pid = read_pid_file(pid_file)
    assert pid == os.getpid()


def test_read_pid_file_missing(tmp_path: Path):
    """Non-existent file returns None."""
    pid_file = str(tmp_path / "nonexistent.pid")
    assert read_pid_file(pid_file) is None


def test_remove_pid_file(tmp_path: Path):
    """Write then remove; file gone."""
    pid_file = str(tmp_path / "daemon.pid")
    write_pid_file(pid_file)
    assert Path(pid_file).exists()
    remove_pid_file(pid_file)
    assert not Path(pid_file).exists()


def test_is_daemon_running_true(tmp_path: Path):
    """Write current PID, returns True."""
    pid_file = str(tmp_path / "daemon.pid")
    write_pid_file(pid_file)
    assert is_daemon_running(pid_file) is True


def test_is_daemon_running_stale(tmp_path: Path):
    """Write non-existent PID, returns False, stale PID file removed."""
    pid_file = str(tmp_path / "daemon.pid")
    # Use a PID that's very unlikely to exist
    Path(pid_file).write_text("999999999")
    assert is_daemon_running(pid_file) is False
    assert not Path(pid_file).exists()


def test_is_daemon_running_no_file(tmp_path: Path):
    """No PID file, returns False."""
    pid_file = str(tmp_path / "nonexistent.pid")
    assert is_daemon_running(pid_file) is False
