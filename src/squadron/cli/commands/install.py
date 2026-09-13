"""install-commands / uninstall-commands — manage Claude Code slash commands."""

from __future__ import annotations

import shutil
from pathlib import Path

import typer
from rich import print as rprint

from squadron.skills.models import InstallReceipt
from squadron.skills.receipts import DEFAULT_RECEIPTS_DIR, read_receipt, write_receipt

# Receipt identity for the bundled command set. One receipt spans every subdirectory the
# install touched, so uninstall can reach them all without guessing which are squadron's.
# Named once here because it is the key both the write and the read address (#65).
COMMANDS_RECEIPT_NAME = "squadron-commands"


def _get_commands_source() -> Path:
    """Locate the bundled commands directory.

    In a wheel install, importlib.resources resolves to the package-internal
    commands/ directory. In a dev/editable install, the force-include hasn't
    taken effect, so we fall back to the repo-root commands/ directory.
    """
    from importlib.resources import files

    pkg_path = Path(str(files("squadron") / "commands"))
    if pkg_path.is_dir() and any(pkg_path.iterdir()):
        return pkg_path

    # Dev fallback: walk up from src/squadron/ to repo root
    repo_root = Path(str(files("squadron"))).parent.parent
    dev_path = repo_root / "commands"
    if dev_path.is_dir():
        return dev_path

    rprint("[red]Error: Could not locate bundled command files.[/red]")
    raise typer.Exit(code=1)


def install_commands(
    target: str = typer.Option(
        "~/.claude/commands",
        "--target",
        help="Target directory for command files",
    ),
    receipts_dir: Path = typer.Option(
        DEFAULT_RECEIPTS_DIR,
        "--receipts-dir",
        help="Directory holding the install receipt",
    ),
) -> None:
    """Install squadron slash commands for Claude Code."""
    source = _get_commands_source()
    target_dir = Path(target).expanduser()

    # What the *previous* install wrote, or None on a first install (or one predating
    # receipts). This is the only authority for what squadron owns: the target
    # subdirectories are shared with the user's own commands, so presence in one proves
    # nothing about who put it there.
    try:
        previous = read_receipt(COMMANDS_RECEIPT_NAME, receipts_dir)
    except ValueError as exc:
        rprint(f"[red]Error reading install receipt: {exc}[/red]")
        raise typer.Exit(code=1) from None
    previously_written: set[str] = set(previous.files_written) if previous else set()

    installed: list[str] = []
    for sub in sorted(source.iterdir()):
        if not sub.is_dir():
            continue
        dest_sub = target_dir / sub.name
        dest_sub.mkdir(parents=True, exist_ok=True)
        for md_file in sorted(sub.glob("*.md")):
            shutil.copy2(md_file, dest_sub / md_file.name)
            installed.append(f"{sub.name}/{md_file.name}")

    # A file is stale only if the previous receipt names it and this bundle no longer
    # does. Anything else in these directories is the user's (issue #65: the old code
    # unlinked every *.md it did not recognize, destroying files like
    # ~/.claude/commands/analysis/mine.md).
    removed: list[str] = []
    for stale in sorted(previously_written - set(installed)):
        stale_path = target_dir / stale
        # A receipt entry for a file the user already deleted is not an error — the
        # desired end state is "absent", and it already holds.
        if stale_path.exists():
            stale_path.unlink()
        removed.append(stale)

    if not installed:
        rprint("[yellow]No command files found to install.[/yellow]")
        return

    write_receipt(
        InstallReceipt(
            pack_name=COMMANDS_RECEIPT_NAME,
            destination=target_dir,
            files_written=installed,
        ),
        receipts_dir,
    )

    rprint(f"[green]Installed {len(installed)} command(s) to {target_dir}:[/green]")
    for name in installed:
        rprint(f"  {name}")

    if removed:
        rprint(f"[yellow]Removed {len(removed)} stale command(s):[/yellow]")
        for name in removed:
            rprint(f"  {name}")


def uninstall_commands(
    target: str = typer.Option(
        "~/.claude/commands",
        "--target",
        help="Target directory to remove commands from",
    ),
    receipts_dir: Path = typer.Option(
        DEFAULT_RECEIPTS_DIR,
        "--receipts-dir",
        help="Directory holding the install receipt",
    ),
) -> None:
    """Remove squadron slash commands from Claude Code."""
    target_dir = Path(target).expanduser()

    try:
        receipt = read_receipt(COMMANDS_RECEIPT_NAME, receipts_dir)
    except ValueError as exc:
        rprint(f"[red]Error reading install receipt: {exc}[/red]")
        raise typer.Exit(code=1) from None

    if receipt is None:
        # A pre-receipt installation. Its files are indistinguishable from the user's own,
        # so removing anything would be guessing — say so rather than guess.
        rprint(
            "[yellow]Nothing to remove — no install receipt found. "
            "Re-run 'sq install-commands' to record one, then uninstall.[/yellow]"
        )
        return

    # Every subdirectory the install touched, not just sq/ (issue #65 finding 1: the old
    # rmtree of sq/ left analysis/ and any other subdirectory behind).
    removed = 0
    touched_dirs: set[Path] = set()
    for relative in receipt.files_written:
        path = target_dir / relative
        touched_dirs.add(path.parent)
        if path.exists():
            path.unlink()
            removed += 1

    # Never rmtree: these directories are shared with the user's own commands. Remove one
    # only once it holds nothing.
    for directory in sorted(touched_dirs, reverse=True):
        if directory.is_dir() and directory != target_dir and not any(directory.iterdir()):
            directory.rmdir()

    (receipts_dir / f"{COMMANDS_RECEIPT_NAME}.toml").unlink(missing_ok=True)

    rprint(f"[green]Removed {removed} command(s) from {target_dir}.[/green]")
