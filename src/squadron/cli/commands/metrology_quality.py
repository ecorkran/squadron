"""Code-quality commands under ``sq metrology`` (slice 403).

Kept in their own module and mounted onto the metrology apps by the parent, like
``metrology_snapshot``. ``slice-ranges`` lands here first; the ``report`` commands
join it.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import typer

from squadron.metrology.errors import MetrologyIdentityError, MetrologyStoreError
from squadron.metrology.identity import derive_project_id
from squadron.metrology.slice_range import SliceRangeResult, record_slice_ranges
from squadron.metrology.slice_range_models import RangeUnresolvedReason
from squadron.metrology.store import MetrologyStore, resolve_store_dir, slice_ranges_record_id
from squadron.review.git_utils import resolve_diff_base

_logger = logging.getLogger(__name__)


def register_quality_commands(metrology_app: typer.Typer, report_app: typer.Typer) -> None:
    """Mount the quality commands onto the parent module's existing apps."""
    _ = report_app  # the report commands mount here as they land

    @metrology_app.command("slice-ranges")
    def slice_ranges(  # pyright: ignore[reportUnusedFunction]
        indices: list[int] = typer.Argument(..., help="Slice indices to resolve, e.g. 403 404"),
        cwd: str | None = typer.Option(
            None, "--cwd", help="Repository root (default: the current directory)"
        ),
        as_json: bool = typer.Option(False, "--json", help="Print the results as JSON"),
    ) -> None:
        """Resolve where each slice landed on the target and record every new landing.

        A landing is found from a merge commit on the target's first-parent history, or
        from the branch's reflog for a fast-forward. Landings are stored the first time
        they resolve and never changed, so a range outlives the reflog that produced it.
        An in-progress branch is not recorded.
        """
        repo_root = Path(cwd).expanduser().resolve() if cwd else Path.cwd().resolve()
        try:
            project_id = derive_project_id(str(repo_root))
            store = MetrologyStore(store_dir=resolve_store_dir(cwd=str(repo_root)))
            results = record_slice_ranges(
                indices, str(repo_root), resolve_diff_base(str(repo_root)), store, project_id
            )
        except MetrologyIdentityError as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(code=1) from exc
        except MetrologyStoreError as exc:
            _logger.error("Slice ranges store failure: %s", exc)
            typer.echo(f"Store error: {exc}", err=True)
            raise typer.Exit(code=1) from exc
        record_path = store.record_location(slice_ranges_record_id(project_id))
        if as_json:
            typer.echo(json.dumps(_as_json(results, record_path), indent=2))
        else:
            for line in _render_lines(results, record_path):
                typer.echo(line)
        failed = [r.index for r in results if r.reason is RangeUnresolvedReason.GIT_ERROR]
        if failed:
            typer.echo(f"Error: git failed while resolving slice(s) {failed}", err=True)
            raise typer.Exit(code=1)


def _render_lines(results: list[SliceRangeResult], record_path: Path) -> list[str]:
    """One line per slice, then the record's path when a record exists."""
    lines = [_render_slice(result) for result in results]
    if record_path.exists():
        lines.append(f"Record: {record_path}")
    return lines


def _render_slice(result: SliceRangeResult) -> str:
    if not result.landings:
        reason = result.reason.value if result.reason is not None else "unknown"
        return f"{result.index}  unresolved: {reason}"
    methods = "+".join(sorted({entry.landing.method.value for entry in result.landings}))
    count = len(result.landings)
    noun = "landing" if count == 1 else "landings"
    new_flag = "  (new)" if any(entry.is_new for entry in result.landings) else ""
    return f"{result.index}  {methods}  {count} {noun}{new_flag}"


def _as_json(results: list[SliceRangeResult], record_path: Path) -> dict[str, object]:
    return {
        "record_path": str(record_path) if record_path.exists() else None,
        "slices": [
            {
                "slice": result.index,
                "reason": result.reason.value if result.reason is not None else None,
                "landings": [
                    {**entry.landing.model_dump(mode="json"), "is_new": entry.is_new}
                    for entry in result.landings
                ],
            }
            for result in results
        ],
    }
