"""[hidden] Emit rendered compaction template instructions to stdout.

Used by the ``/sq:summary`` slash command to obtain deterministic,
template-driven summary instructions for the current Claude Code session.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import typer

from squadron.config.manager import get_config
from squadron.pipeline.summary_render import (
    gather_cf_params,
    resolve_template_instructions,
    resolve_template_suffix,
)

_logger = logging.getLogger(__name__)

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
        raise typer.Exit(code=1) from None

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


def _sibling_projects(cwd: str, project: str) -> set[str]:
    """Return names of sibling checkouts next to ``cwd``, excluding ``project``.

    Used to spot summary files that belong to a sibling project whose name
    extends this one (``squadron`` vs ``squadron-pr``), since the
    ``{project}-*.md`` glob cannot tell a sibling's name from a pipeline key.

    Heuristic, deliberately: it only sees projects checked out next to the
    current one on this machine, so a same-prefix project living elsewhere is
    not caught.
    """
    parent = Path(cwd).resolve().parent
    try:
        return {entry.name for entry in parent.iterdir() if entry.is_dir()} - {project}
    except OSError:
        # Unreadable/removed parent, or a root cwd with nothing above it.
        # Degrade to today's unfiltered behavior rather than failing the restore.
        _logger.warning("cannot enumerate siblings of %s", parent, exc_info=True)
        return set()


def _owning_siblings(matches: list[Path], project: str, siblings: set[str]) -> dict[Path, str]:
    """Map each sibling-owned match to the sibling project that owns it.

    A stem starting with ``{sibling}-`` belongs to that sibling, *unless*
    ``project`` itself starts with ``{sibling}-``. That qualifier is
    load-bearing in the shorter-sibling direction: from the ``squadron-pr``
    checkout, sibling ``squadron`` prefixes every one of this project's own
    stems, and without it every file would be excluded.

    One pass decides both selection and display, so the picker can never mark a
    file excluded that the default would actually select. Longest owner first,
    so a match is attributed to the most specific sibling that claims it.
    """
    owners = sorted(
        (s for s in siblings if not project.startswith(f"{s}-")),
        key=len,
        reverse=True,
    )
    found: dict[Path, str] = {}
    for match in matches:
        for owner in owners:
            if match.stem.startswith(f"{owner}-"):
                found[match] = owner
                break
    return found


def _handle_restore(cwd: str, key: str | None = None) -> None:
    """Find and print a saved summary file for the current project.

    Resolves the project name via CF and globs the summaries directory. Without
    ``key``, prints the most recently modified match that is *not* owned by a
    sibling project whose name extends this one (#103). With ``key``, prints the
    summary saved under that key — sibling-owned files included — matched
    case-insensitively so the same argument resolves identically on
    case-sensitive and case-insensitive filesystems. If multiple summaries
    exist, lists them on stderr, marking the sibling-owned ones.

    Exit codes:
        0 — success; file contents printed to stdout.
        1 — no project resolved, no matching summary files, no file selectable
            by default, or unknown key.
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

    siblings = _sibling_projects(cwd, project)
    owned = _owning_siblings(matches, project, siblings)
    clean = [match for match in matches if match not in owned]

    if len(matches) > 1:
        print(f"Found {len(matches)} summaries for '{project}':", file=sys.stderr)
        for match in matches:
            match_key = _summary_key(match, project)
            owner = owned.get(match)
            suffix = (
                ""
                if owner is None
                else (
                    f"  (excluded from default — matches sibling project "
                    f"'{owner}'; use --key '{match_key}' to restore)"
                )
            )
            print(f"  {match_key}  ({match.name}){suffix}", file=sys.stderr)

    # Default selection draws from `clean` only; `--key` still reaches every
    # match, so an excluded file stays restorable by its exact key (#103).
    if not key and not clean:
        # Distinct from the no-files case above: files exist, they just all
        # belong to siblings. Reporting absence without the remedy would leave
        # the operator stuck, so name the keys that would work.
        keys = ", ".join(f"--key '{_summary_key(m, project)}'" for m in matches)
        print(
            f"Error: no summaries for project '{project}' selectable by default "
            f"({len(matches)} matching "
            f"{'file belongs' if len(matches) == 1 else 'files belong'} to sibling "
            f"projects). Restore one explicitly: {keys}.",
            file=sys.stderr,
        )
        raise typer.Exit(code=1)

    selected = _select_summary(matches, clean, project, key)

    print(f"Using: {selected.name}", file=sys.stderr)
    print(selected.read_text(encoding="utf-8"), end="")


def _select_summary(matches: list[Path], clean: list[Path], project: str, key: str | None) -> Path:
    """Pick the summary to restore: the keyed one, else the most recent clean one.

    Both lists are ordered most-recent-first. The no-key default selects from
    ``clean`` (sibling-owned files excluded, #103); ``--key`` searches the full
    ``matches`` list so an excluded file remains reachable by its exact key.
    Key comparison is case-insensitive; when several files differ only by case,
    the most recent wins, consistent with the no-key default.
    """
    if not key:
        return clean[0]

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
