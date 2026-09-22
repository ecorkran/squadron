"""install-commands / uninstall-commands — install squadron's command set.

What differs between install targets — destination roots, which bundle
subdirectories belong to the target, the on-disk layout, the receipt name —
lives in `squadron.skills.targets`. This module owns the copy/receipt/stale-
removal loop and reads all of it from the `TargetDelivery` it is handed.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich import print as rprint

from squadron.skills.models import InstallReceipt
from squadron.skills.receipts import DEFAULT_RECEIPTS_DIR, read_receipt, write_receipt
from squadron.skills.targets import (
    DELIVERIES,
    CommandTarget,
    TargetDelivery,
    normalize_target,
    receipt_name,
)


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


def _parse_target(ide: str) -> CommandTarget:
    """Resolve the ``--ide`` value, or exit 2 naming the accepted spellings."""
    try:
        return normalize_target(ide)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from None


def _resolve_destination(
    delivery: TargetDelivery, target: str | None, *, local: bool
) -> tuple[Path, bool]:
    """Where an install writes, and whether ``--local`` was honored.

    ``--target`` wins over ``--local``; the caller reports the override rather than
    letting the ignored flag pass silently. Uninstall does not use this — it takes its
    destination from the receipt (D6).
    """
    if target is not None:
        return Path(target).expanduser(), False
    return delivery.resolve_root(local=local), local


def install_commands(
    target: str | None = typer.Option(
        None,
        "--target",
        help="Target directory for command files (defaults to the target's own root)",
    ),
    ide: str = typer.Option(
        CommandTarget.CLAUDE.value,
        "--ide",
        help="Which runtime to install for: claude, agents (aliases: codex, openai)",
    ),
    local: bool = typer.Option(
        False,
        "--local",
        help="Install into this project rather than for the whole machine",
    ),
    receipts_dir: Path = typer.Option(
        DEFAULT_RECEIPTS_DIR,
        "--receipts-dir",
        help="Directory holding the install receipt",
    ),
) -> None:
    """Install squadron's commands for Claude Code or an agent-skills runtime."""
    install_for_target(
        target=target,
        command_target=_parse_target(ide),
        local=local,
        receipts_dir=receipts_dir,
    )


def install_for_target(
    *,
    command_target: CommandTarget = CommandTarget.CLAUDE,
    target: str | None = None,
    local: bool = False,
    receipts_dir: Path | None = None,
) -> None:
    """Install one target's commands. The Typer command's body, callable in-process.

    ``install_commands`` cannot be called directly from Python: unsupplied Typer
    parameters arrive as ``OptionInfo`` objects rather than their defaults, so setup's
    in-process install goes through here instead.
    """
    delivery = DELIVERIES[command_target]
    if receipts_dir is None:
        receipts_dir = DEFAULT_RECEIPTS_DIR

    source = _get_commands_source()
    target_dir, local_honored = _resolve_destination(delivery, target, local=local)
    if local and not local_honored:
        rprint(f"[yellow]--local ignored: --target {target_dir} takes precedence.[/yellow]")
    pack_name = receipt_name(command_target, local=local_honored)

    # What the *previous* install wrote, or None on a first install (or one predating
    # receipts). This is the only authority for what squadron owns: the target
    # subdirectories are shared with the user's own commands, so presence in one proves
    # nothing about who put it there.
    try:
        previous = read_receipt(pack_name, receipts_dir)
    except ValueError as exc:
        rprint(f"[red]Error reading install receipt: {exc}[/red]")
        raise typer.Exit(code=1) from None
    previously_written: set[str] = set(previous.files_written) if previous else set()

    # Only the subdirectories this target claims. Walking every directory under the
    # bundle would sweep the agents tree into ~/.claude/commands (D8).
    installed: list[str] = []
    for sub_name in delivery.bundle_subdirs:
        sub = source / sub_name
        if not sub.is_dir():
            continue
        installed.extend(delivery.layout(sub, target_dir))

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
            pack_name=pack_name,
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
    target: str | None = typer.Option(
        None,
        "--target",
        help="Directory to remove commands from (defaults to the target's own root)",
    ),
    ide: str = typer.Option(
        CommandTarget.CLAUDE.value,
        "--ide",
        help="Which runtime to uninstall from: claude, agents (aliases: codex, openai)",
    ),
    local: bool = typer.Option(
        False,
        "--local",
        help="Uninstall from this project rather than from the whole machine",
    ),
    receipts_dir: Path = typer.Option(
        DEFAULT_RECEIPTS_DIR,
        "--receipts-dir",
        help="Directory holding the install receipt",
    ),
) -> None:
    """Remove squadron's commands from Claude Code or an agent-skills runtime."""
    command_target = _parse_target(ide)
    pack_name = receipt_name(command_target, local=local)

    try:
        receipt = read_receipt(pack_name, receipts_dir)
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

    # The receipt's own destination is where the files are, which is not necessarily
    # where this invocation's flags resolve to: a --local install records an absolute
    # path, so uninstalling from a different working directory would otherwise look for
    # the files somewhere they were never written and report success having removed
    # nothing (D6).
    destination = receipt.destination
    if target is not None:
        requested = Path(target).expanduser()
        if requested != destination:
            rprint(
                f"[red]--target {requested} does not match the recorded install "
                f"destination {destination}.[/red]\n"
                "[red]Nothing was removed. Re-run without --target to uninstall from "
                "the recorded destination.[/red]"
            )
            raise typer.Exit(code=1)

    # Every subdirectory the install touched, not just sq/ (issue #65 finding 1: the old
    # rmtree of sq/ left analysis/ and any other subdirectory behind).
    removed = 0
    touched_dirs: set[Path] = set()
    for relative in receipt.files_written:
        path = destination / relative
        touched_dirs.add(path.parent)
        if path.exists():
            path.unlink()
            removed += 1

    # Never rmtree: these directories are shared with the user's own commands. Remove one
    # only once it holds nothing. Deepest first, so a skill's agents/ subdirectory is
    # gone before its parent is tested for emptiness.
    for directory in sorted(touched_dirs, key=lambda p: len(p.parts), reverse=True):
        while (
            directory.is_dir()
            and directory != destination
            and destination in directory.parents
            and not any(directory.iterdir())
        ):
            directory.rmdir()
            directory = directory.parent

    (receipts_dir / f"{pack_name}.toml").unlink(missing_ok=True)

    rprint(f"[green]Removed {removed} command(s) from {destination}.[/green]")
