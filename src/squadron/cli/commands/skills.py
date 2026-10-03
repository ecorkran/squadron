"""skills sub-app — manage skill packs via skills.toml manifests."""

from __future__ import annotations

from pathlib import Path
from typing import NoReturn

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from squadron.cli.commands.install_options import parse_ide_option, report_skipped_entries
from squadron.skills.installer import install_pack
from squadron.skills.manifest import (
    PROJECT_MANIFEST_NAME,
    SkillsManifest,
    load,
    load_effective,
    user_manifest_path,
)
from squadron.skills.models import SkillSourceError
from squadron.skills.pack_layouts import PACK_LAYOUTS
from squadron.skills.receipts import default_receipts_dir, read_receipt, remove_receipt_files
from squadron.skills.targets import DELIVERIES, CommandTarget, receipt_name

skills_app = typer.Typer(name="skills", help="Manage skill packs.", no_args_is_help=True)

_IDE_HELP = "Which runtime the pack is for: claude, agents (aliases: codex, openai)"
_LOCAL_HELP = "Use this project's directory rather than the machine-wide one"


def _require_manifest() -> NoReturn:
    """Print actionable message and exit — always raises typer.Exit."""
    rprint(
        "[yellow]No skills.toml found. Create one at "
        "~/.config/squadron/skills.toml to manage skill packs.[/yellow]"
    )
    raise typer.Exit(code=1)


def _load_manifest() -> SkillsManifest:
    """The effective manifest, or exit 1 with the reason."""
    try:
        manifest = load_effective(cwd=Path.cwd())
    except ValueError as exc:
        rprint(f"[red]Error loading skills.toml: {exc}[/red]")
        raise typer.Exit(code=1) from None
    if manifest is None:
        _require_manifest()
    return manifest


def _resolve_root(
    target: CommandTarget, commands_dir: Path | None, *, local: bool
) -> tuple[Path, bool]:
    """The pack root for ``target``, and whether ``--local`` was honored.

    ``--commands-dir`` wins over ``--local`` and the override is reported, never
    silent — the same rule ``install-commands`` applies to ``--target`` (D1).
    """
    if commands_dir is not None:
        if local:
            rprint(f"[yellow]--local ignored: --commands-dir {commands_dir} takes precedence.[/yellow]")
        return commands_dir, False
    return DELIVERIES[target].resolve_root(local=local), local


@skills_app.command()
def install(
    pack_name: str = typer.Argument(..., help="Name of the pack to install"),
    ide: str = typer.Option(CommandTarget.CLAUDE.value, "--ide", help=_IDE_HELP),
    local: bool = typer.Option(False, "--local", help=_LOCAL_HELP),
    commands_dir: Path | None = typer.Option(
        None,
        "--commands-dir",
        help="Destination directory, overriding --ide's root and --local",
    ),
    receipts_dir: Path | None = typer.Option(
        None,
        "--receipts-dir",
        help="Directory where the install receipt is written (default: ~/.config/squadron/receipts)",
    ),
) -> None:
    """Install a skill pack from the active manifest."""
    target = parse_ide_option(ide)
    manifest = _load_manifest()
    if pack_name not in manifest.packs:
        available = ", ".join(sorted(manifest.packs)) or "(none)"
        rprint(f"[red]Pack '{pack_name}' not found in skills.toml. Available: {available}[/red]")
        raise typer.Exit(code=1)

    root, local_honored = _resolve_root(target, commands_dir, local=local)
    entry = manifest.packs[pack_name]
    try:
        result = install_pack(
            pack_name, entry, root, receipts_dir=receipts_dir, target=target, local=local_honored
        )
    except SkillSourceError as exc:
        rprint(f"[red]Error: {exc}[/red]")
        raise typer.Exit(code=1) from None

    count = len(result.files_written)
    rprint(f"[green]Installed pack '{pack_name}': {count} file(s) → {result.destination}[/green]")


@skills_app.command()
def uninstall(
    pack_name: str = typer.Argument(..., help="Name of the pack to uninstall"),
    ide: str = typer.Option(CommandTarget.CLAUDE.value, "--ide", help=_IDE_HELP),
    local: bool = typer.Option(False, "--local", help=_LOCAL_HELP),
    commands_dir: Path | None = typer.Option(
        None,
        "--commands-dir",
        help="Directory the pack was installed into; must match the receipt",
    ),
    receipts_dir: Path | None = typer.Option(
        None,
        "--receipts-dir",
        help="Directory holding the install receipt (default: ~/.config/squadron/receipts)",
    ),
) -> None:
    """Remove a skill pack's installed files using its install receipt."""
    target = parse_ide_option(ide)
    receipts_dir = receipts_dir or default_receipts_dir()
    _, local_honored = _resolve_root(target, commands_dir, local=local)
    receipt_key = receipt_name(pack_name, target, local=local_honored)
    try:
        receipt = read_receipt(receipt_key, receipts_dir)
    except ValueError as exc:
        rprint(f"[red]Error reading receipt for '{pack_name}': {exc}[/red]")
        raise typer.Exit(code=1) from None

    if receipt is None:
        rprint(
            f"[red]Pack '{pack_name}' is not installed (no receipt found). "
            "Use 'sq skills list' to check status.[/red]"
        )
        raise typer.Exit(code=1)

    # The receipt is the authority for where the files are (925 D6). A given
    # --commands-dir only checks it: the recorded destination must lie within it.
    destination = receipt.destination
    if commands_dir is not None:
        requested = commands_dir.expanduser().resolve()
        resolved = destination.resolve()
        if requested != resolved and requested not in resolved.parents:
            rprint(
                f"[red]--commands-dir {requested} does not match the recorded install "
                f"destination {destination}. Nothing was removed.[/red]"
            )
            raise typer.Exit(code=1)

    removal = remove_receipt_files(receipt)
    report_skipped_entries(removal)
    removed = removal.removed
    # A Claude prefix directory is the pack's own; drop it once empty, but leave it if
    # the user has unrelated files there. Shared roots are never removed (F001).
    owned = receipt.surface in PACK_LAYOUTS[target].owned_destination_surfaces
    if owned and destination.is_dir() and not any(destination.iterdir()):
        destination.rmdir()

    (receipts_dir / f"{receipt_key}.toml").unlink(missing_ok=True)

    rprint(
        f"[green]Uninstalled pack '{pack_name}': {removed} file(s) removed from {destination}[/green]"
    )


@skills_app.command(name="list")
def list_packs(
    ide: str = typer.Option(CommandTarget.CLAUDE.value, "--ide", help=_IDE_HELP),
    local: bool = typer.Option(False, "--local", help=_LOCAL_HELP),
    commands_dir: Path | None = typer.Option(
        None,
        "--commands-dir",
        help="Directory to check for installed packs, overriding --ide's root and --local",
    ),
) -> None:
    """List skill packs from the active manifest with install status."""
    target = parse_ide_option(ide)
    manifest = _load_manifest()
    root, _ = _resolve_root(target, commands_dir, local=local)
    layout = PACK_LAYOUTS[target]

    table = Table(title="Skill Packs")
    table.add_column("Pack", style="bold")
    table.add_column("Source")
    table.add_column("Surface")
    table.add_column("Status")
    table.add_column("Origin")

    for name, entry in sorted(manifest.packs.items()):
        if entry.prefix is not None:
            surface = f"prefix: {entry.prefix}"
        else:
            surface = f"dispatch_file: {entry.dispatch_file}"

        installed = layout.installed_path(entry, root) is not None
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

    user_path = user_manifest_path()
    if user_path.exists():
        try:
            user_m = load(user_path)
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
