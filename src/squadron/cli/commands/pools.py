"""pools command — inspect and manage model pools."""

from __future__ import annotations

import logging

import typer
from rich.console import Console
from rich.table import Table

from squadron.pipeline.intelligence.pools import (
    DefaultPoolBackend,
    PoolNotFoundError,
    get_all_pools,
    load_builtin_pools,
)
from squadron.pipeline.state import SchemaVersionError, StateManager

_logger = logging.getLogger(__name__)

pools_app = typer.Typer(
    name="pools",
    help="Inspect and manage model pools.",
    invoke_without_command=True,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _get_pool_or_exit(name: str) -> object:
    """Return the named pool or print an error and exit 1."""
    backend = DefaultPoolBackend()
    try:
        return backend.get_pool(name)
    except PoolNotFoundError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc


# ---------------------------------------------------------------------------
# sq pools / sq pools list
# ---------------------------------------------------------------------------


def _show_pools() -> None:
    """Print all available pools as a Rich table."""
    all_pools = get_all_pools()
    if not all_pools:
        typer.echo("No model pools configured.")
        return

    builtin = load_builtin_pools()
    console = Console()
    table = Table(show_header=True, header_style="bold")
    table.add_column("Name", style="cyan")
    table.add_column("Strategy")
    table.add_column("Members", justify="right")
    table.add_column("Source", style="dim")

    for name, pool in sorted(all_pools.items()):
        if name not in builtin:
            source = "(user)"
        elif pool != builtin.get(name):
            source = "(user override)"
        else:
            source = ""
        table.add_row(name, pool.strategy, str(len(pool.models)), source)

    console.print(table)


@pools_app.callback(invoke_without_command=True)
def pools_default(ctx: typer.Context) -> None:
    """Show model pools, or run a subcommand."""
    if ctx.invoked_subcommand is not None:
        return
    _show_pools()


@pools_app.command("list")
def pools_list(
    name: str | None = typer.Argument(None, help="Pool name to inspect (optional)."),
) -> None:
    """List all available model pools, or show detail for a specific pool."""
    if name is None:
        # No argument: show all pools
        _show_pools()
    else:
        # With name: show pool detail
        _show_pool_detail(name)


def _show_pool_detail(name: str) -> None:
    """Print members and recent selections for a named pool."""
    pool = _get_pool_or_exit(name)

    console = Console()
    console.print(f"[bold cyan]{pool.name}[/bold cyan]")  # type: ignore[union-attr]
    if pool.description:  # type: ignore[union-attr]
        console.print(f"  {pool.description}")
    console.print(f"  Strategy: {pool.strategy}")  # type: ignore[union-attr]
    if pool.weights:  # type: ignore[union-attr]
        console.print(f"  Weights: {pool.weights}")

    console.print("\n[bold]Members:[/bold]")
    from squadron.models.aliases import get_all_aliases

    aliases = get_all_aliases()
    member_table = Table(show_header=True, header_style="bold")
    member_table.add_column("Alias", style="cyan")
    member_table.add_column("Model ID")
    member_table.add_column("Cost Tier", style="dim")

    for member in pool.models:  # type: ignore[union-attr]
        alias_info = aliases.get(member)
        if alias_info:
            model_id = alias_info.get("model", "")
            cost_tier = alias_info.get("cost_tier", "")
            member_table.add_row(member, str(model_id), str(cost_tier))
        else:
            member_table.add_row(member, "", "")

    console.print(member_table)

    # Recent selections from run state files
    console.print("\n[bold]Recent selections:[/bold]")
    state_mgr = StateManager()
    recent_selections: list[dict[str, object]] = []
    try:
        runs = state_mgr.list_runs()
        for run in runs[:20]:
            for entry in run.pool_selections:
                if entry.get("pool_name") == name:
                    recent_selections.append(entry)
    except (SchemaVersionError, OSError) as exc:
        _logger.warning("Could not read some run state files: %s", exc)

    if not recent_selections:
        console.print("  (no recent selections)")
    else:
        selections_table = Table(show_header=True, header_style="bold")
        selections_table.add_column("Timestamp")
        selections_table.add_column("Step")
        selections_table.add_column("Selected Alias", style="cyan")

        for entry in recent_selections[-10:]:
            selections_table.add_row(
                str(entry.get("timestamp")),
                str(entry.get("step_name")),
                str(entry.get("selected_alias")),
            )

        console.print(selections_table)


# ---------------------------------------------------------------------------
# sq pools reset <name>
# ---------------------------------------------------------------------------


@pools_app.command("reset")
def pools_reset(name: str = typer.Argument(..., help="Pool name to reset.")) -> None:
    """Clear the round-robin state for a named pool."""
    # Verify pool exists before touching state
    _get_pool_or_exit(name)

    backend = DefaultPoolBackend()
    backend.reset_pool_state(name)
    typer.echo(f"Reset round-robin state for pool '{name}'.")
