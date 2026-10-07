"""Integration smoke test: spawn → list → task → shutdown via DaemonClient mock."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from typer.testing import CliRunner

from squadron.cli.app import app


def test_spawn_list_task_shutdown_sequence() -> None:
    """Full CLI lifecycle using mocked DaemonClient responses."""
    runner = CliRunner()

    mock_client = MagicMock()
    mock_client.spawn = AsyncMock(
        return_value={
            "name": "test-agent",
            "agent_type": "sdk",
            "provider": "sdk",
            "state": "idle",
        }
    )
    mock_client.list_agents = AsyncMock(
        return_value=[
            {
                "name": "test-agent",
                "agent_type": "sdk",
                "provider": "sdk",
                "state": "idle",
            }
        ]
    )
    mock_client.send_message = AsyncMock(
        return_value=[
            {
                "id": "msg-1",
                "sender": "test-agent",
                "content": "echo: hello",
                "message_type": "chat",
                "timestamp": "2026-02-28T00:00:00",
                "metadata": {},
            }
        ]
    )
    mock_client.shutdown_agent = AsyncMock(return_value=None)
    mock_client.close = AsyncMock()

    targets = [
        "squadron.cli.commands.spawn.DaemonClient",
        "squadron.cli.commands.list.DaemonClient",
        "squadron.cli.commands.task.DaemonClient",
        "squadron.cli.commands.shutdown.DaemonClient",
    ]
    patches = [patch(t, return_value=mock_client) for t in targets]
    for p in patches:
        p.start()

    try:
        # 1. Spawn agent
        result = runner.invoke(app, ["spawn", "--name", "test-agent", "--type", "sdk"])
        assert result.exit_code == 0, f"spawn failed:\n{result.output}"
        assert "test-agent" in result.output

        # 2. List: agent appears
        result = runner.invoke(app, ["agents", "list"])
        assert result.exit_code == 0, f"list failed:\n{result.output}"
        assert "test-agent" in result.output

        # 3. Task: send prompt, get response
        result = runner.invoke(app, ["task", "test-agent", "hello"])
        assert result.exit_code == 0, f"task failed:\n{result.output}"
        assert "echo: hello" in result.output

        # 4. Shutdown: agent removed
        result = runner.invoke(app, ["shutdown", "test-agent"])
        assert result.exit_code == 0, f"shutdown:\n{result.output}"
        assert "shut down" in result.output.lower()

        # After shutdown, list returns empty
        mock_client.list_agents.return_value = []
        result = runner.invoke(app, ["agents", "list"])
        assert result.exit_code == 0
        assert "No agents running" in result.output
    finally:
        for p in patches:
            p.stop()
