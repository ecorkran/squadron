"""list command — display active agents in a rich table."""

from __future__ import annotations

import asyncio
from typing import Any

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from squadron.client.http import DaemonClient, DaemonNotRunningError
from squadron.core.models import AgentState

_STATE_COLORS: dict[str, str] = {
    AgentState.idle: "green",
    AgentState.processing: "yellow",
    AgentState.terminated: "red",
    AgentState.failed: "red",
    AgentState.restarting: "cyan",
}


def list_agents(
    state: str | None = typer.Option(None, "--state", help="Filter by agent state"),
    provider: str | None = typer.Option(None, "--provider", help="Filter by provider"),
) -> None:
    """List active agents."""
    asyncio.run(_list_agents(state, provider))


async def _list_agents(state_filter: str | None, provider_filter: str | None) -> None:
    client = DaemonClient()
    try:
        agents: list[dict[str, Any]] = await client.list_agents(
            state=state_filter, provider=provider_filter
        )
    except DaemonNotRunningError:
        rprint("[red]Error: Daemon is not running. Start it with: sq serve[/red]")
        raise typer.Exit(code=1) from None
    finally:
        await client.close()

    if not agents:
        typer.echo("No agents running.")
        return

    table = Table(title="Active Agents")
    table.add_column("Name", style="bold")
    table.add_column("Type")
    table.add_column("Provider")
    table.add_column("State")

    for info in agents:
        agent_state = info.get("state", "unknown")
        color = _STATE_COLORS.get(agent_state, "white")
        table.add_row(
            info["name"],
            info["agent_type"],
            info["provider"],
            f"[{color}]{agent_state}[/{color}]",
        )

    Console().print(table)
