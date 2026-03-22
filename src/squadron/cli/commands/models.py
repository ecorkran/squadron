"""models command — model aliases and endpoint queries."""

from __future__ import annotations

import asyncio

import httpx
import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from squadron.models.aliases import BUILT_IN_ALIASES, get_all_aliases
from squadron.providers.profiles import get_profile

models_app = typer.Typer(
    name="models",
    help="View model aliases or query provider endpoints.",
    invoke_without_command=True,
)


def _show_aliases() -> None:
    """Display the alias table."""
    all_aliases = get_all_aliases()
    if not all_aliases:
        typer.echo("No model aliases configured.")
        return

    console = Console()
    table = Table(show_header=True, header_style="bold")
    table.add_column("Alias", style="cyan")
    table.add_column("Profile")
    table.add_column("Model ID")
    table.add_column("Source", style="dim")

    for name, alias in sorted(all_aliases.items()):
        source = "(user)" if name not in BUILT_IN_ALIASES else ""
        if name in BUILT_IN_ALIASES and alias != BUILT_IN_ALIASES[name]:
            source = "(user override)"
        table.add_row(name, alias["profile"], alias["model"], source)

    console.print(table)


@models_app.callback(invoke_without_command=True)
def models_default(
    ctx: typer.Context,
    profile: str | None = typer.Option(
        None,
        "--profile",
        help="Query models from a provider endpoint (e.g. openrouter, local)",
    ),
    base_url: str | None = typer.Option(
        None,
        "--base-url",
        help="Query models from an OpenAI-compatible base URL",
    ),
) -> None:
    """Show model aliases, or query a provider endpoint with --profile/--base-url."""
    # If a subcommand was invoked, let it handle things
    if ctx.invoked_subcommand is not None:
        return

    # No flags → show aliases
    if profile is None and base_url is None:
        _show_aliases()
        return

    # Flags → query endpoint
    resolved_url = base_url
    if resolved_url is None:
        try:
            p = get_profile(profile)  # type: ignore[arg-type]
            resolved_url = p.base_url
        except KeyError as exc:
            rprint(f"[red]Error: {exc}[/red]")
            raise typer.Exit(code=1) from exc

    if resolved_url is None:
        rprint("[red]Error: profile has no base_url configured[/red]")
        raise typer.Exit(code=1)

    asyncio.run(_fetch_models(resolved_url))


@models_app.command("list")
def models_list() -> None:
    """List available model aliases."""
    _show_aliases()


async def _fetch_models(base_url: str) -> None:
    url = base_url.rstrip("/") + "/models"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
    except httpx.ConnectError:
        rprint(f"[red]Error: could not connect to {base_url}[/red]")
        raise typer.Exit(code=1)
    except Exception as exc:
        rprint(f"[red]Error: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    model_list = data.get("data", [])
    if not model_list:
        rprint("[yellow]No models found.[/yellow]")
        return

    rprint(f"[bold]Models at {base_url}:[/bold]")
    for entry in model_list:
        rprint(f"  {entry['id']}")
