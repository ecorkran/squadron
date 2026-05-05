"""Tests for the shutdown CLI command (daemon client version)."""

from __future__ import annotations

from unittest.mock import MagicMock

from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.client.http import DaemonNotRunningError
from squadron.core.agent_registry import AgentNotFoundError


def _invoke(runner: CliRunner, *args: str):  # type: ignore[no-untyped-def]
    return runner.invoke(app, ["shutdown", *args])


class TestShutdownCommand:
    def test_individual_shutdown_success(
        self, cli_runner: CliRunner, patch_daemon_client: MagicMock
    ) -> None:
        patch_daemon_client.shutdown_agent.return_value = None
        result = _invoke(cli_runner, "myagent")
        assert result.exit_code == 0, result.output
        assert "shut down" in result.output.lower()

    def test_individual_agent_not_found(
        self, cli_runner: CliRunner, patch_daemon_client: MagicMock
    ) -> None:
        patch_daemon_client.shutdown_agent.side_effect = AgentNotFoundError("ghost")
        result = _invoke(cli_runner, "ghost")
        assert result.exit_code == 1
        assert "No agent named" in result.output

    def test_bulk_shutdown_all_succeed(
        self, cli_runner: CliRunner, patch_daemon_client: MagicMock
    ) -> None:
        patch_daemon_client.shutdown_all.return_value = {
            "succeeded": ["a", "b"],
            "failed": {},
        }
        result = _invoke(cli_runner, "--all")
        assert result.exit_code == 0, result.output
        assert "2 succeeded" in result.output

    def test_bulk_shutdown_with_failures(
        self, cli_runner: CliRunner, patch_daemon_client: MagicMock
    ) -> None:
        patch_daemon_client.shutdown_all.return_value = {
            "succeeded": ["a"],
            "failed": {"b": "connection lost"},
        }
        result = _invoke(cli_runner, "--all")
        assert result.exit_code == 0, result.output
        assert "1 succeeded" in result.output
        assert "1 failed" in result.output

    def test_daemon_not_running(self, cli_runner: CliRunner, patch_daemon_client: MagicMock) -> None:
        patch_daemon_client.shutdown_agent.side_effect = DaemonNotRunningError()
        result = _invoke(cli_runner, "myagent")
        assert result.exit_code == 1
        assert "not running" in result.output.lower()

    def test_neither_name_nor_all_shows_error(
        self, cli_runner: CliRunner, patch_daemon_client: MagicMock
    ) -> None:
        result = _invoke(cli_runner)
        assert result.exit_code == 1
