"""task command — send a prompt to a named agent and display the response."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import typer
from rich import print as rprint

from squadron.client.http import DaemonClient, DaemonNotRunningError
from squadron.core.agent_registry import AgentNotFoundError

_TOOL_PREVIEW_LENGTH = 80


def task(
    agent_name: str = typer.Argument(help="Name of the agent to task"),
    prompt: str = typer.Argument(help="Task prompt to send"),
) -> None:
    """Send a task to a named agent and display the response."""
    asyncio.run(_task(agent_name, prompt))


async def _task(agent_name: str, prompt: str) -> None:
    client = DaemonClient()
    try:
        messages = await client.send_message(agent_name, prompt)
        _display_messages(messages)
    except DaemonNotRunningError:
        rprint("[red]Error: Daemon is not running. Start it with: sq serve[/red]")
        raise typer.Exit(code=1) from None
    except AgentNotFoundError:
        rprint(f"[red]Error: No agent named '{agent_name}'. Use 'sq list' to see active agents.[/red]")
        raise typer.Exit(code=1) from None
    finally:
        await client.close()


def _display_messages(messages: list[dict[str, Any]]) -> None:
    multi = len(messages) > 1
    for msg in messages:
        metadata = msg.get("metadata", {})
        if multi:
            rprint(f"[dim]\\[{msg['sender']}][/dim]", end=" ")
        if metadata.get("type") == "tool_use":
            tool_name = metadata.get("tool_name", "tool")
            raw_input = metadata.get("tool_input", {})
            preview = json.dumps(raw_input)[:_TOOL_PREVIEW_LENGTH]
            if len(json.dumps(raw_input)) > _TOOL_PREVIEW_LENGTH:
                preview += "…"
            typer.echo(f"[tool:{tool_name}] {preview}")
        else:
            typer.echo(msg["content"])
