"""Tests for the message CLI command."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.client.http import DaemonNotRunningError
from tests.cli.conftest import make_message_dict


def _invoke(runner: CliRunner, *args: str):  # type: ignore[no-untyped-def]
    return runner.invoke(app, ["message", *args])


class TestMessageCommand:
    def test_message_displays_response(
        self, cli_runner: CliRunner, patch_daemon_client: MagicMock
    ) -> None:
        patch_daemon_client.send_message.return_value = [make_message_dict("Hello from agent")]
        # Need to also patch message command's DaemonClient
        with patch(
            "squadron.cli.commands.message.DaemonClient",
            return_value=patch_daemon_client,
        ):
            result = _invoke(cli_runner, "myagent", "say hello")
        assert result.exit_code == 0, result.output
        assert "Hello from agent" in result.output

    def test_message_daemon_not_running(
        self, cli_runner: CliRunner, patch_daemon_client: MagicMock
    ) -> None:
        patch_daemon_client.send_message.side_effect = DaemonNotRunningError()
        with patch(
            "squadron.cli.commands.message.DaemonClient",
            return_value=patch_daemon_client,
        ):
            result = _invoke(cli_runner, "myagent", "hello")
        assert result.exit_code == 1
        assert "not running" in result.output.lower()
