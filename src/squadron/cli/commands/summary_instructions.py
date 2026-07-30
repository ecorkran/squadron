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
    key: str = typer.Option(
        None,
        "--key",
        hidden=True,
        help="Restore the summary saved under this key instead of the most recent.",
    ),
    project: bool = typer.Option(False, "--project", hidden=True),
) -> None:
    """[hidden] Print rendered compaction template instructions (or suffix)."""
    if project:
        _handle_project(cwd)
        return

    if restore:
        _handle_restore(cwd, key=key)
        return

    # Template name resolution: explicit arg > config > "minimal"
    if not template:
        config_val = get_config("compact.template", cwd=cwd)
        template = config_val if isinstance(config_val, str) and config_val else "minimal"

    try:
        if suffix:
            rendered = resolve_template_suffix(template, cwd=cwd)
        else:
            rendered = resolve_template_instructions(template, cwd=cwd)
    except FileNotFoundError:
        print(f"Error: template '{template}' not found.", file=sys.stderr)
        raise typer.Exit(code=1)

    print(rendered)


def _handle_project(cwd: str) -> None:
    """Print the CF project name for the current working directory.

    Exit codes:
        0 — success; project name printed to stdout.
        1 — project name could not be resolved.
    """
    params = gather_cf_params(cwd)
    project = params.get("project")
    if not project:
        print("Error: cannot resolve project name from CWD.", file=sys.stderr)
        raise typer.Exit(code=1)
    print(project)


def _summary_key(path: Path, project: str) -> str:
    """Return the pipeline key a summary file is saved under.

    Files are named ``{project}-{key}.md``; the key is what ``--key`` matches
    and what the multi-summary picker lists.
    """
    return path.stem.removeprefix(f"{project}-")


def _handle_restore(cwd: str, key: str | None = None) -> None:
    """Find and print a saved summary file for the current project.

    Resolves the project name via CF and globs the summaries directory. Without
    ``key``, prints the most recently modified match. With ``key``, prints the
    summary saved under that key, matched case-insensitively so the same
    argument resolves identically on case-sensitive and case-insensitive
    filesystems. If multiple summaries exist, lists them on stderr.

    Exit codes:
        0 — success; file contents printed to stdout.
        1 — no project resolved, no matching summary files, or unknown key.
    """
    params = gather_cf_params(cwd)
    project = params.get("project")
    if not isinstance(project, str) or not project:
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
        for match in matches:
            print(f"  {_summary_key(match, project)}  ({match.name})", file=sys.stderr)

    selected = _select_summary(matches, project, key)

    print(f"Using: {selected.name}", file=sys.stderr)
    print(selected.read_text(encoding="utf-8"), end="")


def _select_summary(matches: list[Path], project: str, key: str | None) -> Path:
    """Pick the summary to restore: the keyed one, else the most recent.

    ``matches`` is ordered most-recent-first. Key comparison is
    case-insensitive; when several files differ only by case, the most recent
    wins, consistent with the no-key default.
    """
    if not key:
        return matches[0]

    wanted = key.casefold()
    for match in matches:
        if _summary_key(match, project).casefold() == wanted:
            return match

    available = ", ".join(_summary_key(m, project) for m in matches)
    print(
        f"Error: no summary saved under key '{key}' for project '{project}'.\n"
        f"  Available keys: {available}",
        file=sys.stderr,
    )
    raise typer.Exit(code=1)
