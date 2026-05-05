"""Tests for the spawn CLI command (daemon client version)."""

from __future__ import annotations

from unittest.mock import MagicMock

from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.client.http import DaemonNotRunningError
from tests.cli.conftest import make_agent_dict


def _invoke(runner: CliRunner, *args: str):  # type: ignore[no-untyped-def]
    return runner.invoke(app, ["spawn", *args])


class TestSpawnCommand:
    def test_minimal_args_success(self, cli_runner: CliRunner, patch_daemon_client: MagicMock) -> None:
        patch_daemon_client.spawn.return_value = make_agent_dict("test")
        result = _invoke(cli_runner, "--name", "test")
        assert result.exit_code == 0, result.output
        assert "test" in result.output

    def test_daemon_not_running(self, cli_runner: CliRunner, patch_daemon_client: MagicMock) -> None:
        patch_daemon_client.spawn.side_effect = DaemonNotRunningError()
        result = _invoke(cli_runner, "--name", "test")
        assert result.exit_code == 1
        assert "not running" in result.output.lower()

    def test_spawn_error(self, cli_runner: CliRunner, patch_daemon_client: MagicMock) -> None:
        patch_daemon_client.spawn.side_effect = Exception("boom")
        result = _invoke(cli_runner, "--name", "test")
        assert result.exit_code == 1
        assert "boom" in result.output
