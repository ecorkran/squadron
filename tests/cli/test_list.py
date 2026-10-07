"""Tests for sq agents list (daemon client version)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.client.http import DaemonNotRunningError
from squadron.core.agent_registry import AgentNotFoundError
from tests.cli.conftest import make_agent_dict


def _invoke(runner: CliRunner, *args: str):  # type: ignore[no-untyped-def]
    return runner.invoke(app, ["agents", "list", *args])


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


class TestAgentsListRename:
    """sq list moved to sq agents list with no alias (slice 199 D14)."""

    def test_bare_sq_list_is_not_a_command(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(app, ["list"])
        assert result.exit_code != 0
        assert "No such command" in result.output

    def test_state_and_provider_filters_pass_through(
        self, cli_runner: CliRunner, patch_daemon_client: MagicMock
    ) -> None:
        patch_daemon_client.list_agents.return_value = []
        result = _invoke(cli_runner, "--state", "idle", "--provider", "openai")
        assert result.exit_code == 0, result.output
        patch_daemon_client.list_agents.assert_awaited_once_with(state="idle", provider="openai")

    @pytest.mark.parametrize(
        ("args", "method"),
        [
            (["task", "ghost", "hello"], "send_message"),
            (["message", "ghost", "hello"], "send_message"),
            (["shutdown", "ghost"], "shutdown_agent"),
        ],
    )
    def test_agent_not_found_errors_name_sq_agents_list(
        self,
        cli_runner: CliRunner,
        patch_daemon_client: MagicMock,
        args: list[str],
        method: str,
    ) -> None:
        getattr(patch_daemon_client, method).side_effect = AgentNotFoundError("ghost")
        with patch("squadron.cli.commands.message.DaemonClient", return_value=patch_daemon_client):
            result = cli_runner.invoke(app, args)
        assert result.exit_code == 1
        assert "Use 'sq agents list' to see active agents" in " ".join(result.output.split())


_REPO = Path(__file__).parents[2]


def test_slash_command_runs_sq_agents_list() -> None:
    text = (_REPO / "commands/sq/list.md").read_text()
    assert "sq agents list $ARGUMENTS" in text
    assert "sq list" not in text


def test_agents_skill_runs_sq_agents_list() -> None:
    # Agents skills append the user's arguments in prose; $ARGUMENTS is Claude-only.
    text = (_REPO / "commands/agents/sq-list/SKILL.md").read_text()
    assert "Run `sq agents list`" in text
    assert "sq list" not in text
