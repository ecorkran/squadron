"""Tests for the serve command — status, stop, and start checks."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from squadron.cli.app import app

runner = CliRunner()


def test_serve_status_not_running(tmp_path: Path):
    """No PID file → prints 'not running'."""
    pid_path = str(tmp_path / "daemon.pid")
    with patch("squadron.cli.commands.serve.DaemonConfig") as mock_cfg_cls:
        cfg = mock_cfg_cls.return_value
        cfg.pid_path = pid_path
        cfg.socket_path = str(tmp_path / "daemon.sock")
        cfg.port = 7862

        result = runner.invoke(app, ["serve", "--status"])
        assert "not running" in result.output.lower()


def test_serve_status_running(tmp_path: Path):
    """PID file with live PID → prints 'running'."""
    pid_path = str(tmp_path / "daemon.pid")
    Path(pid_path).write_text(str(os.getpid()))
    with patch("squadron.cli.commands.serve.DaemonConfig") as mock_cfg_cls:
        cfg = mock_cfg_cls.return_value
        cfg.pid_path = pid_path
        cfg.socket_path = str(tmp_path / "daemon.sock")
        cfg.port = 7862

        result = runner.invoke(app, ["serve", "--status"])
        assert "running" in result.output.lower()
        assert str(os.getpid()) in result.output


def test_serve_stop_sends_sigterm(tmp_path: Path):
    """Mock os.kill; verify SIGTERM sent to PID from file."""
    import signal as sig_mod

    pid_path = str(tmp_path / "daemon.pid")
    Path(pid_path).write_text(str(os.getpid()))
    with (
        patch("squadron.cli.commands.serve.DaemonConfig") as mock_cfg_cls,
        patch("squadron.cli.commands.serve.os.kill") as mock_kill,
    ):
        cfg = mock_cfg_cls.return_value
        cfg.pid_path = pid_path
        cfg.socket_path = str(tmp_path / "daemon.sock")
        cfg.port = 7862

        result = runner.invoke(app, ["serve", "--stop"])
        assert result.exit_code == 0
        # os.kill called for is_daemon_running (sig 0) and SIGTERM
        sigterm_calls = [c for c in mock_kill.call_args_list if c[0][1] == sig_mod.SIGTERM]
        assert len(sigterm_calls) == 1
        assert sigterm_calls[0][0][0] == os.getpid()


def test_serve_stop_not_running(tmp_path: Path):
    """No PID file → prints error, exits non-zero."""
    pid_path = str(tmp_path / "nonexistent.pid")
    with patch("squadron.cli.commands.serve.DaemonConfig") as mock_cfg_cls:
        cfg = mock_cfg_cls.return_value
        cfg.pid_path = pid_path
        cfg.socket_path = str(tmp_path / "daemon.sock")
        cfg.port = 7862

        result = runner.invoke(app, ["serve", "--stop"])
        assert result.exit_code == 1
        assert "not running" in result.output.lower()


def test_serve_already_running(tmp_path: Path):
    """PID file with live PID → prints error about existing daemon."""
    pid_path = str(tmp_path / "daemon.pid")
    Path(pid_path).write_text(str(os.getpid()))
    with patch("squadron.cli.commands.serve.DaemonConfig") as mock_cfg_cls:
        cfg = mock_cfg_cls.return_value
        cfg.pid_path = pid_path
        cfg.socket_path = str(tmp_path / "daemon.sock")
        cfg.port = 7862

        result = runner.invoke(app, ["serve"])
        assert result.exit_code == 1
        assert "already running" in result.output.lower()
