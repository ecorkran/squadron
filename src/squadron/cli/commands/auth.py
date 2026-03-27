"""auth subcommand — credential validation and status reporting."""

from __future__ import annotations

import typer
from rich import print as rprint
from rich.table import Table

from squadron.providers.auth import resolve_auth_strategy_for_profile
from squadron.providers.profiles import get_all_profiles, get_profile

auth_app = typer.Typer(
    name="auth",
    help="Credential management.",
    no_args_is_help=True,
)


@auth_app.command("login")
def auth_login(
    profile_name: str = typer.Argument(help="Profile name to validate credentials for"),
) -> None:
    """Validate credentials for the given profile."""
    try:
        profile = get_profile(profile_name)
    except KeyError as exc:
        rprint(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc

    strategy = resolve_auth_strategy_for_profile(profile)
    if strategy.is_valid():
        source = strategy.active_source or "(valid)"
        rprint(f"[green]✓[/green] {profile_name}: authenticated ({source})")
    else:
        rprint(f"[red]✗[/red] {profile_name}: not authenticated")
        rprint(f"  {strategy.setup_hint}")


@auth_app.command("status")
def auth_status() -> None:
    """Show credential state for all configured profiles."""
    profiles = get_all_profiles()

    table = Table(show_header=True, header_style="bold")
    table.add_column("Profile")
    table.add_column("Auth Type")
    table.add_column("Status")
    table.add_column("Source")

    for name, profile in sorted(profiles.items()):
        strategy = resolve_auth_strategy_for_profile(profile)
        if strategy.is_valid():
            status = "[green]✓ authenticated[/green]"
            source = strategy.active_source or ""
        else:
            status = "[red]✗ not authenticated[/red]"
            source = strategy.setup_hint

        table.add_row(name, profile.auth_type, status, source)

    rprint(table)
