"""skills sub-app — manage skill packs via skills.toml manifests."""

from __future__ import annotations

from pathlib import Path
from typing import NoReturn

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from squadron.skills.installer import install_pack
from squadron.skills.manifest import (
    PROJECT_MANIFEST_NAME,
    USER_MANIFEST,
    load,
    load_effective,
)
from squadron.skills.models import SkillSourceError

_DEFAULT_COMMANDS_DIR = Path.home() / ".claude" / "commands"

skills_app = typer.Typer(name="skills", help="Manage skill packs.", no_args_is_help=True)


def _require_manifest() -> NoReturn:
    """Print actionable message and exit — always raises typer.Exit."""
    rprint(
        "[yellow]No skills.toml found. Create one at "
        "~/.config/squadron/skills.toml to manage skill packs.[/yellow]"
    )
    raise typer.Exit(code=1)


@skills_app.command()
def install(
    pack_name: str = typer.Argument(..., help="Name of the pack to install"),
    commands_dir: Path = typer.Option(
        _DEFAULT_COMMANDS_DIR,
        "--commands-dir",
        help="Destination directory for installed commands",
    ),
) -> None:
    """Install a skill pack from the active manifest."""
    try:
        manifest = load_effective(cwd=Path.cwd())
    except ValueError as exc:
        rprint(f"[red]Error loading skills.toml: {exc}[/red]")
        raise typer.Exit(code=1)
    if manifest is None:
        _require_manifest()

    if pack_name not in manifest.packs:
        available = ", ".join(sorted(manifest.packs)) or "(none)"
        rprint(f"[red]Pack '{pack_name}' not found in skills.toml. Available: {available}[/red]")
        raise typer.Exit(code=1)

    entry = manifest.packs[pack_name]
    try:
        result = install_pack(pack_name, entry, commands_dir)
    except SkillSourceError as exc:
        rprint(f"[red]Error: {exc}[/red]")
        raise typer.Exit(code=1)

    count = len(result.files_written)
    rprint(f"[green]Installed pack '{pack_name}': {count} file(s) → {result.destination}[/green]")


@skills_app.command(name="list")
def list_packs(
    commands_dir: Path = typer.Option(
        _DEFAULT_COMMANDS_DIR,
        "--commands-dir",
        help="Commands directory to check for installed packs",
    ),
) -> None:
    """List skill packs from the active manifest with install status."""
    try:
        manifest = load_effective(cwd=Path.cwd())
    except ValueError as exc:
        rprint(f"[red]Error loading skills.toml: {exc}[/red]")
        raise typer.Exit(code=1)
    if manifest is None:
        _require_manifest()

    table = Table(title="Skill Packs")
    table.add_column("Pack", style="bold")
    table.add_column("Source")
    table.add_column("Surface")
    table.add_column("Status")
    table.add_column("Origin")

    for name, entry in sorted(manifest.packs.items()):
        if entry.prefix is not None:
            surface = f"prefix: {entry.prefix}"
            dest = commands_dir / entry.prefix
        else:
            surface = f"dispatch_file: {entry.dispatch_file}"
            dest = commands_dir / "sq" / f"{entry.dispatch_file}.md"

        installed = dest.exists() and (dest.is_dir() and any(dest.iterdir()) or dest.is_file())
        status = "[green]Installed[/green]" if installed else "[dim]Not installed[/dim]"

        origin = manifest.origin if manifest.origin != "merged" else _detect_origin(name)

        table.add_row(name, entry.source, surface, status, origin)

    Console().print(table)


def _detect_origin(pack_name: str) -> str:
    """For merged manifests, report which level declared the pack.

    Project-level is checked first — this matches merge semantics where project
    wins on collision. Errors loading either manifest are silently ignored here
    because _detect_origin is best-effort display info; the earlier load_effective()
    call would have already surfaced any parse errors before we reach this point.
    """
    user_m = None
    proj_m = None

    if USER_MANIFEST.exists():
        try:
            user_m = load(USER_MANIFEST)
        except (ValueError, OSError):
            pass  # best-effort; load_effective already validated on the main path

    project_path = Path.cwd() / PROJECT_MANIFEST_NAME
    if project_path.exists():
        try:
            proj_m = load(project_path)
        except (ValueError, OSError):
            pass  # best-effort; same rationale as above

    if proj_m and pack_name in proj_m.packs:
        return "project"
    if user_m and pack_name in user_m.packs:
        return "user"
    return "unknown"
