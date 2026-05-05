"""Tests for the list CLI command (daemon client version)."""

from __future__ import annotations

from unittest.mock import MagicMock

from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.client.http import DaemonNotRunningError
from tests.cli.conftest import make_agent_dict


def _invoke(runner: CliRunner, *args: str):  # type: ignore[no-untyped-def]
    return runner.invoke(app, ["list", *args])


class TestListCommand:
    def test_empty_shows_no_agents_message(
        self, cli_runner: CliRunner, patch_daemon_client: MagicMock
    ) -> None:
        patch_daemon_client.list_agents.return_value = []
        result = _invoke(cli_runner)
        assert result.exit_code == 0, result.output
        assert "No agents running" in result.output

    def test_two_agents_output_contains_names(
        self, cli_runner: CliRunner, patch_daemon_client: MagicMock
    ) -> None:
        patch_daemon_client.list_agents.return_value = [
            make_agent_dict("agent-one"),
            make_agent_dict("agent-two"),
        ]
        result = _invoke(cli_runner)
        assert result.exit_code == 0, result.output
        assert "agent-one" in result.output
        assert "agent-two" in result.output

    def test_daemon_not_running(self, cli_runner: CliRunner, patch_daemon_client: MagicMock) -> None:
        patch_daemon_client.list_agents.side_effect = DaemonNotRunningError()
        result = _invoke(cli_runner)
        assert result.exit_code == 1
        assert "not running" in result.output.lower()
