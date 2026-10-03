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

from squadron.cli.commands.install_options import parse_ide_option, report_skipped_entries
from squadron.skills.codex_rules import codex_home, remove_sq_rules, write_sq_rules
from squadron.skills.models import InstallReceipt
from squadron.skills.receipts import (
    default_receipts_dir,
    read_receipt,
    remove_receipt_files,
    write_receipt,
)
from squadron.skills.targets import (
    DELIVERIES,
    CommandTarget,
    TargetDelivery,
    receipt_name,
)

#: Receipt base name for the bundled command set (D5).
BUNDLED_RECEIPT_BASE = "squadron-commands"


def get_commands_source() -> Path:
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


def _resolve_destination(
    delivery: TargetDelivery, target: str | None, *, local: bool
) -> tuple[Path, bool]:
    """Where an install writes, and whether ``--local`` was honored.

    ``--target`` wins over ``--local``; the caller reports the override rather than
    letting the ignored flag pass silently. Uninstall does not use this — it takes its
    destination from the receipt (D6).
    """
    if target is not None:
        # Resolved, not merely expanded: the receipt records this path and
        # uninstall compares against it, so a relative or symlinked `--target`
        # would otherwise write a destination that means something different
        # from another working directory.
        return Path(target).expanduser().resolve(), False
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
    receipts_dir: Path | None = typer.Option(
        None,
        "--receipts-dir",
        help="Directory holding the install receipt (default: ~/.config/squadron/receipts)",
    ),
) -> None:
    """Install squadron's commands for Claude Code or an agent-skills runtime."""
    install_for_target(
        target=target,
        command_target=parse_ide_option(ide),
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
        receipts_dir = default_receipts_dir()

    source = get_commands_source()
    target_dir, local_honored = _resolve_destination(delivery, target, local=local)
    if local and not local_honored:
        rprint(f"[yellow]--local ignored: --target {target_dir} takes precedence.[/yellow]")
    pack_name = receipt_name(BUNDLED_RECEIPT_BASE, command_target, local=local_honored)

    # What the *previous* install wrote, or None on a first install (or one predating
    # receipts). This is the only authority for what squadron owns: the target
    # subdirectories are shared with the user's own commands, so presence in one proves
    # nothing about who put it there.
    try:
        previous = read_receipt(pack_name, receipts_dir)
    except ValueError as exc:
        rprint(f"[red]Error reading install receipt: {exc}[/red]")
        raise typer.Exit(code=1) from None
    # Stale-removal only applies where the previous install actually wrote. A receipt
    # records its destination, and `--target` can move it between runs under the same
    # pack name; resolving the old receipt's paths against the *new* destination would
    # delete a same-named file belonging to the user and report removals that never
    # happened. This mirrors the guard uninstall applies (D6).
    same_destination = previous is not None and previous.destination.resolve() == target_dir.resolve()
    previously_written: set[str] = (
        set(previous.files_written) if previous and same_destination else set()
    )
    if previous is not None and not same_destination:
        rprint(
            f"[yellow]Previous install recorded {previous.destination}; installing to "
            f"{target_dir}. Files at the old destination are left alone — "
            f"uninstall them there first if you want them gone.[/yellow]"
        )

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

    if command_target is CommandTarget.AGENTS:
        _ensure_codex_rules()


def _ensure_codex_rules() -> None:
    """Write squadron's own Codex sandbox rules file (issue #127, 928 D9)."""
    home = codex_home()
    if not home.is_dir():
        rprint(
            f"[yellow]No Codex home at {home}; skipped the sandbox rules squadron's "
            f"skills need. Re-run after installing Codex.[/yellow]"
        )
        return
    try:
        rules_path = write_sq_rules(home)
    except OSError as exc:
        # The skills and receipt are already installed; an unwritable rules file must
        # not turn that into a failed install. Say what to fix instead.
        rprint(
            f"[yellow]Installed, but could not write the Codex sandbox rules under {home}: "
            f"{exc}. Fix the permissions and re-run the install.[/yellow]"
        )
        return
    rprint(f"[green]Wrote Codex sandbox rules to {rules_path}[/green]")


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
    receipts_dir: Path | None = typer.Option(
        None,
        "--receipts-dir",
        help="Directory holding the install receipt (default: ~/.config/squadron/receipts)",
    ),
) -> None:
    """Remove squadron's commands from Claude Code or an agent-skills runtime."""
    receipts_dir = receipts_dir or default_receipts_dir()
    command_target = parse_ide_option(ide)

    # `--target` overrides `--local` on install, and the receipt is named for the
    # scope that was *honored*. Uninstall has to resolve the name the same way or
    # the identical flag combination looks up a receipt that was never written,
    # reports "nothing to remove", and sends the user to re-install.
    local_honored = local and target is None
    if local and not local_honored:
        rprint("[yellow]--local ignored: --target takes precedence, as it did on install.[/yellow]")
    pack_name = receipt_name(BUNDLED_RECEIPT_BASE, command_target, local=local_honored)

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
        # Compare canonical paths. `~/x`, `/abs/x`, `x/`, a relative path and a
        # symlinked one all name the same directory; a lexical comparison refuses
        # every spelling but the one originally typed.
        requested = Path(target).expanduser().resolve()
        if requested != destination.resolve():
            rprint(
                f"[red]--target {requested} does not match the recorded install "
                f"destination {destination}.[/red]\n"
                "[red]Nothing was removed. Re-run without --target to uninstall from "
                "the recorded destination.[/red]"
            )
            raise typer.Exit(code=1)

    # Every subdirectory the install touched, not just sq/ (issue #65 finding 1: the old
    # rmtree of sq/ left analysis/ and any other subdirectory behind).
    removal = remove_receipt_files(receipt)
    report_skipped_entries(removal)
    removed = removal.removed

    (receipts_dir / f"{pack_name}.toml").unlink(missing_ok=True)

    rprint(f"[green]Removed {removed} command(s) from {destination}.[/green]")

    # The rules file is machine-wide. Only an uninstall of the default machine install
    # removes it; a --local or --target uninstall leaves it for the machine install
    # that may still need it.
    if command_target is CommandTarget.AGENTS and not local and target is None:
        rules_path = remove_sq_rules(codex_home())
        if rules_path is not None:
            rprint(f"[green]Removed Codex sandbox rules {rules_path}.[/green]")
