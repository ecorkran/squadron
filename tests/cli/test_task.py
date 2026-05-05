"""Tests for the task CLI command (daemon client version)."""

from __future__ import annotations

from unittest.mock import MagicMock

from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.client.http import DaemonNotRunningError
from squadron.core.agent_registry import AgentNotFoundError
from tests.cli.conftest import make_message_dict


def _invoke(runner: CliRunner, *args: str):  # type: ignore[no-untyped-def]
    return runner.invoke(app, ["task", *args])


class TestTaskCommand:
    def test_successful_task_shows_response(
        self, cli_runner: CliRunner, patch_daemon_client: MagicMock
    ) -> None:
        patch_daemon_client.send_message.return_value = [make_message_dict("Hello from agent")]
        result = _invoke(cli_runner, "myagent", "say hello")
        assert result.exit_code == 0, result.output
        assert "Hello from agent" in result.output

    def test_agent_not_found(self, cli_runner: CliRunner, patch_daemon_client: MagicMock) -> None:
        patch_daemon_client.send_message.side_effect = AgentNotFoundError("ghost")
        result = _invoke(cli_runner, "ghost", "hello")
        assert result.exit_code == 1
        assert "No agent named" in result.output

    def test_daemon_not_running(self, cli_runner: CliRunner, patch_daemon_client: MagicMock) -> None:
        patch_daemon_client.send_message.side_effect = DaemonNotRunningError()
        result = _invoke(cli_runner, "myagent", "hello")
        assert result.exit_code == 1
        assert "not running" in result.output.lower()
