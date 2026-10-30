"""Code-quality commands under ``sq metrology`` (slice 403).

Kept in their own module and mounted onto the metrology apps by the parent, like
``metrology_snapshot``. ``slice-ranges`` lands here first; the ``report`` commands
join it.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from pydantic import BaseModel

from squadron.cli.commands.metrology_quality_support import (
    QualityContext,
    commit_exists,
    exit_on_failure,
    first_parent_history,
    load_context,
    take_commit,
)
from squadron.metrology.quality_report.history_report import build_history_report
from squadron.metrology.quality_report.project_report import build_project_report
from squadron.metrology.quality_report.render import (
    render_history_report,
    render_project_report,
    render_slice_report,
)
from squadron.metrology.quality_report.slice_report import (
    TakeSnapshotAt,
    build_slice_report,
    ensure_snapshot,
)
from squadron.metrology.slice_range import SliceRangeResult, record_slice_ranges
from squadron.metrology.slice_range_models import RangeUnresolvedReason
from squadron.metrology.store import slice_ranges_record_id


def register_quality_commands(metrology_app: typer.Typer, report_app: typer.Typer) -> None:
    """Mount the quality commands onto the parent module's existing apps."""
    _mount_slice_ranges(metrology_app)
    _mount_reports(report_app)


def _mount_slice_ranges(metrology_app: typer.Typer) -> None:
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
        with exit_on_failure():
            ctx = load_context(cwd)
            results = record_slice_ranges(
                indices, str(ctx.repo_root), ctx.target, ctx.store, ctx.project_id
            )
        record_path = ctx.store.record_location(slice_ranges_record_id(ctx.project_id))
        if as_json:
            typer.echo(json.dumps(_as_json(results, record_path), indent=2))
        else:
            for line in _render_lines(results, record_path):
                typer.echo(line)
        _exit_if_git_failed(results)


def _exit_if_git_failed(results: list[SliceRangeResult]) -> None:
    failed = [r.index for r in results if r.reason is RangeUnresolvedReason.GIT_ERROR]
    if failed:
        typer.echo(f"Error: git failed while resolving slice(s) {failed}", err=True)
        raise typer.Exit(code=1)


def _emit(report: BaseModel, lines: list[str], as_json: bool) -> None:
    typer.echo(report.model_dump_json(indent=2) if as_json else "\n".join(lines))


def _mount_reports(report_app: typer.Typer) -> None:
    cwd_option = typer.Option(None, "--cwd", help="Repository root (default: the current directory)")
    json_option = typer.Option(False, "--json", help="Print the report model as JSON")

    @report_app.command("slice")
    def report_slice(  # pyright: ignore[reportUnusedFunction]
        index: int = typer.Argument(..., help="Slice index, e.g. 403"),
        cwd: str | None = cwd_option,
        as_json: bool = json_option,
    ) -> None:
        """Report what a slice changed: static figures, audit delta and review findings.

        Resolves and records the slice's landings, then compares the code before and after
        each one. A boundary commit with no stored snapshot is measured from a temp export
        and recorded, so this command writes snapshots and slice ranges. It never runs an audit.
        """
        with exit_on_failure():
            ctx = load_context(cwd)
            [result] = record_slice_ranges(
                [index], str(ctx.repo_root), ctx.target, ctx.store, ctx.project_id
            )
            report = build_slice_report(
                index,
                result,
                ctx.store,
                ctx.project_id,
                lambda sha: commit_exists(ctx.repo_root, sha),
                lambda commit: ensure_snapshot(
                    commit, ctx.repo_root, ctx.store, ctx.project_id, take_commit_for(ctx)
                ),
            )
        _emit(report, render_slice_report(report), as_json)
        _exit_if_git_failed([result])

    @report_app.command("project")
    def report_project(  # pyright: ignore[reportUnusedFunction]
        cwd: str | None = cwd_option, as_json: bool = json_option
    ) -> None:
        """Report the project's current state: latest snapshot, audit baseline and reviews.

        Reviews count toward a slice only when that slice has a stored landing.
        """
        with exit_on_failure():
            ctx = load_context(cwd)
            stored = ctx.store.get_slice_ranges(ctx.project_id)
            resolved = sorted(stored.slices) if stored is not None else []
            report = build_project_report(ctx.store, ctx.project_id, resolved)
        _emit(report, render_project_report(report), as_json)

    @report_app.command("history")
    def report_history(  # pyright: ignore[reportUnusedFunction]
        cwd: str | None = cwd_option, as_json: bool = json_option
    ) -> None:
        """Report snapshots in the target's first-parent order, marking where they break."""
        with exit_on_failure():
            ctx = load_context(cwd)
            history = first_parent_history(ctx.repo_root, ctx.target)
            report = build_history_report(ctx.store, ctx.project_id, history)
        _emit(report, render_history_report(report), as_json)


def take_commit_for(ctx: QualityContext) -> TakeSnapshotAt:
    """A snapshot source bound to *ctx*'s store."""
    return lambda repo_root, commit: take_commit(repo_root, commit, ctx.store)


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
