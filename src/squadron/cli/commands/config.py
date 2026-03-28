"""config subcommand — manage persistent configuration."""

from __future__ import annotations

import typer
from rich import print as rprint

from squadron.config.keys import CONFIG_KEYS
from squadron.config.manager import (
    get_config,
    project_config_path,
    resolve_config_source,
    set_config,
    unset_config,
    user_config_path,
)

config_app = typer.Typer(
    name="config",
    help="Manage persistent configuration.",
    no_args_is_help=True,
)


@config_app.command("set")
def config_set(
    key: str = typer.Argument(help="Config key to set"),
    value: str = typer.Argument(help="Value to set"),
    project: bool = typer.Option(
        False, "--project", help="Write to project-level config"
    ),
    cwd: str = typer.Option(".", "--cwd", help="Working directory"),
) -> None:
    """Set a config value."""
    try:
        set_config(key, value, project=project, cwd=cwd)
    except KeyError as exc:
        rprint(f"[red]Error: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    source = "project" if project else "user"
    rprint(f"Set {key} = {value} ({source} config)")


@config_app.command("unset")
def config_unset(
    key: str = typer.Argument(help="Config key to remove"),
    project: bool = typer.Option(
        False, "--project", help="Remove from project-level config"
    ),
    cwd: str = typer.Option(".", "--cwd", help="Working directory"),
) -> None:
    """Remove a config key, reverting to its default value."""
    try:
        removed = unset_config(key, project=project, cwd=cwd)
    except KeyError as exc:
        rprint(f"[red]Error: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    source = "project" if project else "user"
    if removed:
        rprint(f"Removed {key} from {source} config")
    else:
        rprint(f"{key} is not set in {source} config")


@config_app.command("get")
def config_get(
    key: str = typer.Argument(help="Config key to read"),
    cwd: str = typer.Option(".", "--cwd", help="Working directory"),
) -> None:
    """Show the resolved value of a config key."""
    try:
        val = get_config(key, cwd=cwd)
        source = resolve_config_source(key, cwd=cwd)
    except KeyError as exc:
        rprint(f"[red]Error: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    rprint(f"{key} = {val}  ({source})")


@config_app.command("list")
def config_list(
    cwd: str = typer.Option(".", "--cwd", help="Working directory"),
) -> None:
    """Show all config keys with resolved values."""
    max_key_len = max(len(k) for k in CONFIG_KEYS)
    for key_name in sorted(CONFIG_KEYS):
        try:
            val = get_config(key_name, cwd=cwd)
            source = resolve_config_source(key_name, cwd=cwd)
        except KeyError:
            continue
        display_val = str(val) if val is not None else "(not set)"
        rprint(f"  {key_name:<{max_key_len}}  {display_val:<40}  ({source})")


@config_app.command("path")
def config_path(
    cwd: str = typer.Option(".", "--cwd", help="Working directory"),
) -> None:
    """Show config file locations and existence status."""
    user_path = user_config_path()
    proj_path = project_config_path(cwd)

    user_exists = user_path.is_file()
    proj_exists = proj_path.is_file()

    user_status = "[green]exists[/green]" if user_exists else "[dim]not found[/dim]"
    proj_status = "[green]exists[/green]" if proj_exists else "[dim]not found[/dim]"

    rprint(f"  User:    {user_path}  {user_status}")
    rprint(f"  Project: {proj_path}  {proj_status}")
