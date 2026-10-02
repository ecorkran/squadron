"""auth subcommand — interactive login/logout, credential validation, status."""

from __future__ import annotations

import asyncio
from typing import NoReturn

import typer
from rich import print as rprint
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from squadron.config.manager import get_typed_config
from squadron.providers.auth import (
    AuthStrategy,
    InteractiveLogin,
    resolve_auth_strategy_for_profile,
)
from squadron.providers.codex.login import LOGIN_TIMEOUT_KEY
from squadron.providers.errors import ProviderError
from squadron.providers.profiles import ProviderProfile, get_all_profiles, get_profile

#: soft_wrap: commands and sign-in URLs must reach the terminal unbroken.
_console = Console(soft_wrap=True)

auth_app = typer.Typer(
    name="auth",
    help="Credential management.",
    no_args_is_help=True,
)


@auth_app.command("login")
def auth_login(
    profile_name: str = typer.Argument(help="Profile to log in to, or validate credentials for"),
    device_code: bool = typer.Option(
        False, "--device-code", help="Log in with a device code (SSH / headless machines)"
    ),
    timeout: int | None = typer.Option(
        None,
        "--timeout",
        help=f"Seconds to wait for login to finish (default: config {LOGIN_TIMEOUT_KEY})",
    ),
) -> None:
    """Log in interactively where the profile supports it; otherwise validate credentials."""
    profile = _profile_or_exit(profile_name)
    strategy = resolve_auth_strategy_for_profile(profile)
    if not isinstance(strategy, InteractiveLogin):
        if device_code or timeout is not None:
            _fail(f"profile {profile_name!r} does not support interactive login")
        _report_validity(profile_name, strategy.is_valid(), strategy)
        return

    timeout_s = timeout if timeout is not None else get_typed_config(LOGIN_TIMEOUT_KEY, int)
    try:
        asyncio.run(strategy.login(device_code=device_code, timeout_s=timeout_s, notify=_print_notice))
    except ProviderError as exc:
        _fail(str(exc))
    except KeyboardInterrupt:
        _fail("login cancelled")
    # A completed login is a success even when the account lookup fails (it warned).
    summary = asyncio.run(strategy.account_summary())
    detail = summary or strategy.active_source or "(valid)"
    rprint(f"[green]✓[/green] {escape(profile_name)}: authenticated ({escape(detail)})")


@auth_app.command("logout")
def auth_logout(
    profile_name: str = typer.Argument(help="Profile to log out of"),
) -> None:
    """Log out of a profile that supports interactive login."""
    profile = _profile_or_exit(profile_name)
    strategy = resolve_auth_strategy_for_profile(profile)
    if not isinstance(strategy, InteractiveLogin):
        _fail(f"profile {profile_name!r} does not support interactive login")
    try:
        asyncio.run(strategy.logout())
    except ProviderError as exc:
        _fail(str(exc))
    rprint(f"[green]✓[/green] {escape(profile_name)}: logged out")


def _profile_or_exit(profile_name: str) -> ProviderProfile:
    try:
        return get_profile(profile_name)
    except KeyError as exc:
        rprint(f"[red]Error:[/red] {escape(str(exc))}")
        raise typer.Exit(1) from exc


def _fail(message: str) -> NoReturn:
    _console.print(f"[red]Error:[/red] {escape(message)}")
    raise typer.Exit(1)


def _print_notice(message: str) -> None:
    """``notify`` for interactive login: URLs and codes go to the user, as plain text."""
    _console.print(escape(message))


def _report_validity(profile_name: str, valid: bool, strategy: AuthStrategy) -> None:
    if valid:
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
            if isinstance(strategy, InteractiveLogin):
                source += _account_detail(strategy)
        else:
            status = "[red]✗ not authenticated[/red]"
            source = strategy.setup_hint

        table.add_row(name, profile.auth_type, status, escape(source))

    # Built per call so the table takes the terminal's current width.
    Console().print(table)


def _account_detail(strategy: InteractiveLogin) -> str:
    """`` (<email>, <plan>)`` for the signed-in account, else ``""``.

    A failed lookup already logged a WARNING; the row still shows validity and source.
    """
    summary = asyncio.run(strategy.account_summary())
    return f" ({summary})" if summary is not None else ""
