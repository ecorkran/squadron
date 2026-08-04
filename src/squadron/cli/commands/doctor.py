"""Typer command and rendering for `sq doctor` environment diagnostic."""

from __future__ import annotations

import importlib.metadata
import json
from importlib.metadata import PackageNotFoundError

import typer
from rich.console import Console
from rich.text import Text

from squadron.cli.commands.doctor_checks import (
    SECTION_CONFIG,
    SECTION_INSTALL,
    SECTION_INTEGRATIONS,
    SECTION_PROVIDERS,
    SECTION_SKILLS,
    CheckResult,
    CheckStatus,
    run_all_checks,
)
from squadron.review.git_utils import run_git

_SECTION_ORDER = [
    SECTION_INSTALL,
    SECTION_PROVIDERS,
    SECTION_INTEGRATIONS,
    SECTION_SKILLS,
    SECTION_CONFIG,
]

_STATUS_ICON: dict[CheckStatus, tuple[str, str]] = {
    CheckStatus.OK: ("✓", "green"),
    CheckStatus.MISSING: ("✗", "red"),
    CheckStatus.WARN: ("!", "yellow"),
}


def _render_table(results: list[CheckResult], verbose: bool) -> None:
    console = Console(soft_wrap=True)
    console.print()
    console.print("[bold]Squadron Environment Diagnostic[/bold]")
    console.print("─" * 64)

    sections: dict[str, list[CheckResult]] = {}
    for r in results:
        sections.setdefault(r.section, []).append(r)

    warn_count = sum(1 for r in results if r.status == CheckStatus.WARN)
    missing_count = sum(1 for r in results if r.status == CheckStatus.MISSING)

    for section_name in _SECTION_ORDER:
        rows = sections.get(section_name, [])
        if not rows:
            continue
        console.print(f"\n[bold]{section_name}[/bold]")
        for row in rows:
            if row.status == CheckStatus.WARN and not verbose:
                continue
            icon, color = _STATUS_ICON[row.status]
            name_col = f"{row.name:<28}"
            line = Text()
            line.append(f"  {icon} ", style=color)
            line.append(name_col)
            line.append(row.detail)
            console.print(line)
            # Any row still being rendered here is one the user should act on:
            # non-verbose runs already skipped WARN rows above, so a surviving
            # WARN implies verbose. Show the remedy whenever we have one —
            # printing a problem while withholding its fix is the worst of both.
            if row.fix_hint:
                console.print(f"    [dim]fix: {row.fix_hint}[/dim]")

    console.print()
    console.print("─" * 64)
    if verbose:
        console.print(f"[bold]{missing_count} missing · {warn_count} warnings[/bold]")
    else:
        suffix = f" · {warn_count} warnings (run with -v to show)" if warn_count else ""
        console.print(f"[bold]{missing_count} missing{suffix}[/bold]")
    console.print()


def _render_json(results: list[CheckResult], squadron_version: str) -> None:
    missing = sum(1 for r in results if r.status == CheckStatus.MISSING)
    ok_count = sum(1 for r in results if r.status == CheckStatus.OK)
    warn_count = sum(1 for r in results if r.status == CheckStatus.WARN)
    exit_code = 1 if missing else 0

    output = {
        "squadron_version": squadron_version,
        "exit_code": exit_code,
        "summary": {"ok": ok_count, "missing": missing, "warn": warn_count},
        "checks": [
            {
                "section": r.section,
                "name": r.name,
                "status": str(r.status),
                "detail": r.detail,
                "fix_hint": r.fix_hint,
                "required": r.required,
            }
            for r in results
        ],
    }
    print(json.dumps(output, indent=2))


def _resolve_git_hooks_path() -> str | None:
    """``core.hooksPath`` for the current repo, or None outside a git repo / on error.

    Uses ``run_git`` rather than a raw subprocess call, per the project's own
    convention for shelling out to git. A repo with the key unset returns the
    empty string (not None) so ``check_git_hooks`` can tell "no repo, nothing
    to gate" apart from "repo present, hook not installed."
    """
    repo_check = run_git(["rev-parse", "--is-inside-work-tree"], cwd=".")
    if repo_check is None or repo_check.returncode != 0:
        return None

    process = run_git(["config", "--get", "core.hooksPath"], cwd=".")
    if process is None:
        return None
    return process.stdout.strip()


def doctor(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show WARN-level rows."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
) -> None:
    """Inspect runtime environment and report what is configured."""
    try:
        squadron_version = importlib.metadata.version("squadron-ai")
    except PackageNotFoundError:
        squadron_version = "(dev install)"

    results = run_all_checks(git_hooks_path=_resolve_git_hooks_path())
    exit_code = 1 if any(r.status == CheckStatus.MISSING for r in results) else 0

    if json_output:
        _render_json(results, squadron_version)
    else:
        _render_table(results, verbose)

    raise typer.Exit(exit_code)
