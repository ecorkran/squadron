"""message command — send a message to an agent via the daemon."""

from __future__ import annotations

import asyncio
from typing import Any

import typer
from rich import print as rprint

from squadron.client.http import DaemonClient, DaemonNotRunningError
from squadron.core.agent_registry import AgentNotFoundError


def message(
    agent_name: str = typer.Argument(help="Name of the agent"),
    prompt: str = typer.Argument(help="Message to send"),
) -> None:
    """Send a message to an agent and display the response."""
    asyncio.run(_message(agent_name, prompt))


async def _message(agent_name: str, prompt: str) -> None:
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
    for msg in messages:
        sender = msg.get("sender", "unknown")
        content = msg.get("content", "")
        rprint(f"[dim]\\[{sender}][/dim] {content}")
