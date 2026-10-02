"""models command — model aliases and endpoint queries."""

from __future__ import annotations

import asyncio
from enum import StrEnum

import httpx
import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from squadron.models.aliases import ModelAlias, get_all_aliases, load_builtin_aliases
from squadron.providers.profiles import get_profile

# cost_tier display mapping
_COST_TIER_LABELS: dict[str, str] = {
    "free": "free",
    "cheap": "$",
    "moderate": "$$",
    "expensive": "$$$",
    "subscription": "sub",
}


class ModelSort(StrEnum):
    """Ordering for the alias table."""

    PROFILE = "profile"
    ALIAS = "alias"


#: Display order for profile groups. Deliberately not alphabetical, which
#: would yield gemini/openai/openai-oauth/openrouter/sdk — burying the
#: primary profile last and grouping nothing meaningfully. This order
#: follows how a user reaches for them. Defined once; a profile absent from
#: this list sorts last rather than being dropped.
_PROFILE_ORDER: tuple[str, ...] = (
    "sdk",
    "openai",
    "openai-oauth",
    "gemini",
    "openrouter",
    "local",
)


def _profile_rank(profile: str) -> int:
    """Sort position for a profile, with unknown profiles last."""
    try:
        return _PROFILE_ORDER.index(profile)
    except ValueError:
        # An unrecognized profile (a user-defined one) still appears — at the
        # end, grouped with its peers, never silently omitted.
        return len(_PROFILE_ORDER)


models_app = typer.Typer(
    name="models",
    help="View model aliases or query provider endpoints.",
    invoke_without_command=True,
)


def _show_aliases(*, verbose: bool = False, sort: ModelSort = ModelSort.PROFILE) -> None:
    """Display the alias table.

    Grouped by profile by default: with 30-odd aliases across five
    profiles, a flat alias sort scatters related models — the Gemini
    variants land apart, and codex/codex-agent/codex-spark split because
    their profiles differ. ``sort=ALIAS`` restores the flat ordering.
    """
    all_aliases = get_all_aliases()
    if not all_aliases:
        typer.echo("No model aliases configured.")
        return

    console = Console()
    table = Table(show_header=True, header_style="bold")
    table.add_column("Alias", style="cyan")
    table.add_column("Profile")
    table.add_column("Model ID")

    if verbose:
        table.add_column("Private", style="dim")
        table.add_column("Cost")
        table.add_column("In $/1M")
        table.add_column("Out $/1M")
        table.add_column("Notes", style="dim")

    table.add_column("Source", style="dim")

    builtin_aliases = load_builtin_aliases()
    if sort is ModelSort.ALIAS:
        rows = sorted(all_aliases.items())
    else:
        rows = sorted(
            all_aliases.items(),
            key=lambda item: (_profile_rank(item[1]["profile"]), item[1]["profile"], item[0]),
        )
    for name, alias in rows:
        source = "(user)" if name not in builtin_aliases else ""
        if name in builtin_aliases and alias != builtin_aliases[name]:
            source = "(user override)"

        row: list[str] = [name, alias["profile"], alias["model"]]

        if verbose:
            row.extend(_verbose_columns(alias))

        row.append(source)
        table.add_row(*row)

    console.print(table)


def _verbose_columns(alias: ModelAlias) -> list[str]:
    """Return the five verbose-mode column values for an alias."""
    private_val = alias.get("private")
    private_str = "yes" if private_val is True else ("no" if private_val is False else "")

    cost_tier = alias.get("cost_tier", "")
    cost_str = _COST_TIER_LABELS.get(cost_tier, "")

    pricing = alias.get("pricing")
    if pricing is not None:
        in_price = pricing.get("input")
        out_price = pricing.get("output")
        in_str = f"${in_price:.2f}" if in_price is not None else ""
        out_str = f"${out_price:.2f}" if out_price is not None else ""
    else:
        in_str = ""
        out_str = ""

    notes = alias.get("notes", "")[:30]

    return [private_str, cost_str, in_str, out_str, notes]


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
    verbose: bool = typer.Option(
        False,
        "-v",
        "--verbose",
        help="Show metadata columns (Private, Cost, Pricing, Notes)",
    ),
    sort: ModelSort = typer.Option(
        ModelSort.PROFILE,
        "--sort",
        help="Group by profile (default) or sort flat by alias name",
    ),
) -> None:
    """Show model aliases, or query a provider endpoint with --profile/--base-url."""
    # If a subcommand was invoked, let it handle things
    if ctx.invoked_subcommand is not None:
        return

    # No flags → show aliases
    if profile is None and base_url is None:
        _show_aliases(verbose=verbose, sort=sort)
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
def models_list(
    verbose: bool = typer.Option(
        False,
        "-v",
        "--verbose",
        help="Show metadata columns (Private, Cost, Pricing, Notes)",
    ),
    sort: ModelSort = typer.Option(
        ModelSort.PROFILE,
        "--sort",
        help="Group by profile (default) or sort flat by alias name",
    ),
) -> None:
    """List available model aliases."""
    _show_aliases(verbose=verbose, sort=sort)


async def _fetch_models(base_url: str) -> None:
    url = base_url.rstrip("/") + "/models"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
    except httpx.ConnectError:
        rprint(f"[red]Error: could not connect to {base_url}[/red]")
        raise typer.Exit(code=1) from None
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
