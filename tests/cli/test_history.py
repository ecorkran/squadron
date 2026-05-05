"""Tests for the history CLI command."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.client.http import DaemonNotRunningError
from tests.cli.conftest import make_message_dict


def _invoke(runner: CliRunner, *args: str):  # type: ignore[no-untyped-def]
    return runner.invoke(app, ["history", *args])


def _patch_history_client(mock_client: MagicMock):  # type: ignore[no-untyped-def]
    """Patch DaemonClient in history command module."""
    return patch(
        "squadron.cli.commands.history.DaemonClient",
        return_value=mock_client,
    )


class TestHistoryCommand:
    def test_history_displays_messages(
        self, cli_runner: CliRunner, patch_daemon_client: MagicMock
    ) -> None:
        patch_daemon_client.get_history.return_value = [
            make_message_dict("hello", sender="human"),
            make_message_dict("response", sender="agent1"),
        ]
        with _patch_history_client(patch_daemon_client):
            result = _invoke(cli_runner, "agent1")
        assert result.exit_code == 0, result.output
        assert "hello" in result.output
        assert "response" in result.output

    def test_history_daemon_not_running(
        self, cli_runner: CliRunner, patch_daemon_client: MagicMock
    ) -> None:
        patch_daemon_client.get_history.side_effect = DaemonNotRunningError()
        with _patch_history_client(patch_daemon_client):
            result = _invoke(cli_runner, "agent1")
        assert result.exit_code == 1
        assert "not running" in result.output.lower()

    def test_history_with_limit(self, cli_runner: CliRunner, patch_daemon_client: MagicMock) -> None:
        patch_daemon_client.get_history.return_value = [make_message_dict("latest")]
        with _patch_history_client(patch_daemon_client):
            result = _invoke(cli_runner, "agent1", "--limit", "5")
        assert result.exit_code == 0, result.output
        patch_daemon_client.get_history.assert_called_once_with("agent1", limit=5)
