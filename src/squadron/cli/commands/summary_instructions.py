"""[hidden] Emit rendered compaction template instructions to stdout.

Used by the ``/sq:summary`` slash command to obtain deterministic,
template-driven summary instructions for the current Claude Code session.
"""

from __future__ import annotations

import sys
from pathlib import Path

import typer

from squadron.config.manager import get_config
from squadron.pipeline.summary_render import (
    gather_cf_params,
    resolve_template_instructions,
    resolve_template_suffix,
)

# Conventional directory where pipeline summary files are stored.
_SUMMARIES_DIR = Path.home() / ".config" / "squadron" / "runs" / "summaries"


def summary_instructions(
    template: str = typer.Argument(
        None,
        help="Compaction template name (e.g. 'minimal', 'minimal-sdk').",
    ),
    cwd: str = typer.Option(".", "--cwd", hidden=True),
    suffix: bool = typer.Option(False, "--suffix", hidden=True),
    restore: bool = typer.Option(False, "--restore", hidden=True),
) -> None:
    """[hidden] Print rendered compaction template instructions (or suffix)."""
    if restore:
        _handle_restore(cwd)
        return

    # Template name resolution: explicit arg > config > "minimal"
    if not template:
        config_val = get_config("compact.template", cwd=cwd)
        template = (
            config_val if isinstance(config_val, str) and config_val else "minimal"
        )

    try:
        if suffix:
            rendered = resolve_template_suffix(template, cwd=cwd)
        else:
            rendered = resolve_template_instructions(template, cwd=cwd)
    except FileNotFoundError:
        print(f"Error: template '{template}' not found.", file=sys.stderr)
        raise typer.Exit(code=1)

    print(rendered)


def _handle_restore(cwd: str) -> None:
    """Find and print the latest summary file for the current project.

    Resolves the project name via CF, globs the summaries directory, and
    prints the contents of the most recently modified matching file to stdout.
    If multiple pipelines have summary files, lists them on stderr and uses
    the most recent.

    Exit codes:
        0 — success; file contents printed to stdout.
        1 — no project resolved, or no matching summary files found.
    """
    params = gather_cf_params(cwd)
    project = params.get("project")
    if not project:
        print("Error: cannot resolve project name from CWD.", file=sys.stderr)
        raise typer.Exit(code=1)

    matches = sorted(
        _SUMMARIES_DIR.glob(f"{project}-*.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if not matches:
        print(
            f"Error: no summary files found for project '{project}'.",
            file=sys.stderr,
        )
        raise typer.Exit(code=1)

    if len(matches) > 1:
        print(f"Found {len(matches)} summaries for '{project}':", file=sys.stderr)
        for m in matches:
            pipeline = m.stem.removeprefix(f"{project}-")
            print(f"  {pipeline}  ({m.name})", file=sys.stderr)
        print(f"Using most recent: {matches[0].name}", file=sys.stderr)

    print(matches[0].read_text(encoding="utf-8"), end="")
