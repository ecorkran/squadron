"""Typer command for `sq setup` — interactive install orchestrator."""

from __future__ import annotations

import logging

import typer
from rich.console import Console
from rich.text import Text

from squadron.cli.commands.doctor import resolve_git_hooks_path
from squadron.cli.commands.doctor_checks import (
    CheckStatus,
    run_all_checks,
)
from squadron.cli.commands.setup_install import (
    AUTO_INSTALL_CHECKS,
    CF_INIT_HINT,
    installer_for,
    run_install,
)
from squadron.cli.commands.setup_steps import (
    SetupStep,
    StepKind,
    build_steps,
)

logger = logging.getLogger(__name__)

_ICON: dict[StepKind, tuple[str, str]] = {
    StepKind.ALREADY_DONE: ("✓", "green"),
    StepKind.INSTALL: ("✗", "red"),
    StepKind.CONFIGURE: ("✗", "red"),
    StepKind.OPTIONAL: ("!", "yellow"),
}

_MAX_RECHECKS = 5


def _render_check_only(steps: list[SetupStep]) -> int:
    """Print one summary line per step. Returns count of INSTALL+CONFIGURE steps."""
    console = Console(soft_wrap=True)
    missing_count = 0
    for step in steps:
        icon, color = _ICON[step.kind]
        line = Text()
        line.append(f"  {icon} ", style=color)
        line.append(f"{step.title:<32}")
        line.append(step.detail)
        console.print(line)
        if step.kind in {StepKind.INSTALL, StepKind.CONFIGURE}:
            missing_count += 1
    return missing_count


def _render_step_block(console: Console, step: SetupStep, n: int, total: int, verbose: bool) -> None:
    """Print a full step block (header, detail, command, docs)."""
    icon, color = _ICON[step.kind]
    console.print()
    header = Text()
    header.append(f"{icon} ", style=color)
    header.append(f"Step {n}/{total} — ", style="bold")
    header.append(step.title, style="bold")
    console.print(header)
    console.print("─" * 48)
    console.print(f"  {step.detail}")
    if step.command:
        console.print()
        console.print(f"  [bold]$ {step.command}[/bold]")
    if verbose and step.explanation:
        console.print()
        console.print(f"  [dim]{step.explanation}[/dim]")
    if step.docs_anchor:
        console.print(f"  [dim]see: {step.docs_anchor}[/dim]")


def _render_non_interactive(steps: list[SetupStep], verbose: bool) -> int:
    """Emit every step block without prompting. Returns INSTALL+CONFIGURE count."""
    console = Console(soft_wrap=True)
    total = len(steps)
    missing_count = 0
    for n, step in enumerate(steps, start=1):
        _render_step_block(console, step, n, total, verbose)
        if step.kind in {StepKind.INSTALL, StepKind.CONFIGURE}:
            missing_count += 1
    console.print()
    return missing_count


def _run_interactive(steps: list[SetupStep], verbose: bool) -> int:
    """Walk through steps interactively with per-step rechecks.

    Returns the final INSTALL+CONFIGURE count (after rechecks).
    Raises typer.Exit(2) if the user quits.
    """
    console = Console(soft_wrap=True)
    total = len(steps)

    for n, step in enumerate(steps, start=1):
        if step.kind == StepKind.ALREADY_DONE:
            icon, color = _ICON[step.kind]
            line = Text()
            line.append(f"  {icon} ", style=color)
            line.append(f"{step.title} — already done")
            console.print(line)
            continue

        if step.kind == StepKind.OPTIONAL and not verbose:
            # D11: the gate installs itself. Auto-install steps run without a
            # prompt instead of hiding behind --verbose like other optional
            # steps — a normal setup run must leave a working gate.
            if step.check_name in AUTO_INSTALL_CHECKS and installer_for(step.check_name):
                outcome = run_install(step.check_name)
                style = "green" if outcome.succeeded else "yellow"
                console.print(f"  [{style}]{outcome.message}[/{style}]")
            continue

        _render_step_block(console, step, n, total, verbose)

        # Optional steps with no recheck are informational only — render and
        # continue without trapping the user in a prompt they can't satisfy.
        if step.kind == StepKind.OPTIONAL and step.recheck is None:
            continue

        # Steps that can install themselves offer to do so. These are all
        # user-global and idempotent, so making the user retype a command we
        # already know is friction with no upside.
        can_install = installer_for(step.check_name) is not None
        prompt_text = (
            "\n[Enter] to install, 's' to skip, 'q' to quit"
            if can_install
            else "\n[Enter] when done, 's' to skip, 'q' to quit"
        )

        attempt = 0
        while True:
            response = (
                typer.prompt(
                    prompt_text,
                    default="",
                    show_default=False,
                )
                .strip()
                .lower()
            )

            if response == "q":
                raise typer.Exit(2)

            if response == "s":
                break

            if can_install:
                console.print("  [dim]installing…[/dim]")
                outcome = run_install(step.check_name)
                if outcome.succeeded:
                    console.print(f"  [green]✓ {outcome.message}[/green]")
                else:
                    # Fall through to the recheck below rather than looping on
                    # a failure the user may have just fixed in another shell.
                    console.print(f"  [yellow]{outcome.message}[/yellow]")

            # Empty → recheck
            if step.recheck is not None:
                try:
                    result = step.recheck()
                except Exception:
                    logger.exception("recheck failed for step %r", step.check_name)
                    console.print("  [yellow]recheck error — continuing[/yellow]")
                    break

                if result.status == CheckStatus.OK:
                    console.print("  [green]✓ detected — moving on[/green]")
                    break

                attempt += 1
                if attempt >= _MAX_RECHECKS:
                    console.print("  [yellow]still not detected — skipping[/yellow]")
                    break

                console.print(
                    f"  [yellow]still not detected (attempt {attempt}/{_MAX_RECHECKS})[/yellow]"
                )
            else:
                # No recheck function; trust the user
                break

    # Final summary — re-run all checks (in addition to per-step rechecks above)
    console.print()
    console.print("[bold]─── Final check ──────────────────────────────────────────────[/bold]")
    try:
        final_results = run_all_checks(git_hooks_path=resolve_git_hooks_path())
    except Exception:
        logger.exception("final run_all_checks failed")
        console.print("[red]Could not run final check — try `sq doctor` directly.[/red]")
        return 1

    missing_count = sum(1 for r in final_results if r.status == CheckStatus.MISSING)
    warn_count = sum(1 for r in final_results if r.status == CheckStatus.WARN)
    if missing_count == 0:
        console.print("[green bold]✓ All required checks pass.[/green bold]")
    else:
        console.print(f"[red bold]✗ {missing_count} required item(s) still missing.[/red bold]")
    if warn_count:
        console.print(f"  [yellow]{warn_count} optional item(s) skipped.[/yellow]")
    console.print()
    # Global setup ends here by design: cf init is per-project, so it is the
    # user's call where to run it.
    console.print(CF_INIT_HINT)
    console.print()
    return missing_count


def setup(
    non_interactive: bool = typer.Option(
        False, "--non-interactive", "-y", help="Emit all steps without prompting."
    ),
    check_only: bool = typer.Option(
        False, "--check-only", help="One-line summary per step; exit like sq doctor."
    ),
    profile: str | None = typer.Option(
        None, "--profile", help="Limit Providers section to one profile."
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show OPTIONAL steps and explanations."
    ),
) -> None:
    """Walk through the full Squadron install sequence interactively."""
    try:
        results = run_all_checks(git_hooks_path=resolve_git_hooks_path())
    except Exception:
        logger.exception("sq setup: run_all_checks raised unexpectedly")
        typer.echo("sq setup: internal error during checks; try `sq doctor` directly", err=True)
        raise typer.Exit(3) from None

    try:
        steps = build_steps(results, profile)
    except ValueError as exc:
        from squadron.providers.profiles import get_all_profiles

        available = ", ".join(sorted(get_all_profiles().keys())) or "(none)"
        typer.echo(f"sq setup: {exc}", err=True)
        typer.echo(f"Available profiles: {available}", err=True)
        raise typer.Exit(64) from None

    if check_only:
        missing_count = _render_check_only(steps)
        raise typer.Exit(1 if missing_count else 0)

    if non_interactive:
        missing_count = _render_non_interactive(steps, verbose)
        raise typer.Exit(1 if missing_count else 0)

    # Interactive (default)
    missing_count = _run_interactive(steps, verbose)
    raise typer.Exit(1 if missing_count else 0)
