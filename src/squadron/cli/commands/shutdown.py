"""shutdown command — gracefully stop one or all agents."""

from __future__ import annotations

import asyncio

import typer
from rich import print as rprint

from squadron.client.http import DaemonClient, DaemonNotRunningError
from squadron.core.agent_registry import AgentNotFoundError


def shutdown(
    agent_name: str | None = typer.Argument(default=None, help="Agent to shut down"),
    all_agents: bool = typer.Option(False, "--all", help="Shut down all agents"),
) -> None:
    """Shut down one agent or all agents."""
    if agent_name is None and not all_agents:
        rprint("[red]Error: Provide an agent name or use --all.[/red]")
        raise typer.Exit(code=1)
    if agent_name is not None and all_agents:
        rprint("[red]Error: Provide either an agent name or --all, not both.[/red]")
        raise typer.Exit(code=1)

    if all_agents:
        asyncio.run(_shutdown_all())
    else:
        asyncio.run(_shutdown_one(agent_name))  # type: ignore[arg-type]


async def _shutdown_one(name: str) -> None:
    client = DaemonClient()
    try:
        await client.shutdown_agent(name)
        rprint(f"[green]Agent '{name}' shut down.[/green]")
    except DaemonNotRunningError:
        rprint("[red]Error: Daemon is not running. Start it with: sq serve[/red]")
        raise typer.Exit(code=1)
    except AgentNotFoundError:
        rprint(f"[red]Error: No agent named '{name}'. Use 'sq list' to see active agents.[/red]")
        raise typer.Exit(code=1)
    finally:
        await client.close()


async def _shutdown_all() -> None:
    client = DaemonClient()
    try:
        report = await client.shutdown_all()
        succeeded = report.get("succeeded", [])
        failed = report.get("failed", {})
        total = len(succeeded) + len(failed)
        rprint(f"Shut down {total} agents. {len(succeeded)} succeeded, {len(failed)} failed.")
        for name, error in failed.items():
            rprint(f"  [red]✗ {name}: {error}[/red]")
    except DaemonNotRunningError:
        rprint("[red]Error: Daemon is not running. Start it with: sq serve[/red]")
        raise typer.Exit(code=1)
    finally:
        await client.close()
