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
    CheckResult,
    CheckStatus,
    run_all_checks,
)

_SECTION_ORDER = [SECTION_INSTALL, SECTION_PROVIDERS, SECTION_INTEGRATIONS, SECTION_CONFIG]

_STATUS_ICON: dict[CheckStatus, tuple[str, str]] = {
    CheckStatus.OK: ("✓", "green"),
    CheckStatus.MISSING: ("✗", "red"),
    CheckStatus.WARN: ("!", "yellow"),
}


def _render_table(results: list[CheckResult], verbose: bool) -> None:
    console = Console()
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
            if row.fix_hint and row.status != CheckStatus.WARN or (row.fix_hint and verbose):
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


def doctor(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show WARN-level rows."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
) -> None:
    """Inspect runtime environment and report what is configured."""
    try:
        squadron_version = importlib.metadata.version("squadron-ai")
    except PackageNotFoundError:
        squadron_version = "(dev install)"

    results = run_all_checks()
    exit_code = 1 if any(r.status == CheckStatus.MISSING for r in results) else 0

    if json_output:
        _render_json(results, squadron_version)
    else:
        _render_table(results, verbose)

    raise typer.Exit(exit_code)
