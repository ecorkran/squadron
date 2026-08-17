"""history command — display conversation history for an agent."""

from __future__ import annotations

import asyncio
from typing import Any

import typer
from rich import print as rprint

from squadron.client.http import DaemonClient, DaemonNotRunningError


def history(
    agent_name: str = typer.Argument(help="Name of the agent"),
    limit: int | None = typer.Option(None, "--limit", help="Show only the last N messages"),
) -> None:
    """Display conversation history for an agent."""
    asyncio.run(_history(agent_name, limit))


async def _history(agent_name: str, limit: int | None) -> None:
    client = DaemonClient()
    try:
        messages = await client.get_history(agent_name, limit=limit)
        _display_history(messages)
    except DaemonNotRunningError:
        rprint("[red]Error: Daemon is not running. Start it with: sq serve[/red]")
        raise typer.Exit(code=1) from None
    finally:
        await client.close()


def _display_history(messages: list[dict[str, Any]]) -> None:
    if not messages:
        typer.echo("No messages in history.")
        return

    for msg in messages:
        sender = msg.get("sender", "unknown")
        content = msg.get("content", "")
        timestamp = msg.get("timestamp", "")
        rprint(f"[dim]{timestamp}[/dim] [bold]\\[{sender}][/bold] {content}")
