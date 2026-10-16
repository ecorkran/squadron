"""``sq stats``: what runs and reviews spent (slice 175 D8).

Reads only. The cores in ``squadron.stats`` build the reports; this module picks the
input, renders a table or JSON, and maps load errors to exit codes.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import typer
from rich import get_console

from squadron.cli.stats_effort_views import render_slice_report, render_slices_report
from squadron.cli.stats_producer_views import render_producers_report
from squadron.cli.stats_runs_views import render_runs_report
from squadron.cli.stats_views import (
    render_reviews_report,
    render_run_report,
    reviews_report_json,
    run_report_json,
)
from squadron.config.manager import get_typed_config
from squadron.pipeline.state import StateManager
from squadron.pipeline.steps import StepTypeName
from squadron.review.git_utils import run_git
from squadron.review.persistence import REVIEWS_DIR
from squadron.stats.effort_report import slice_effort_report
from squadron.stats.effort_rollup import slices_effort_report
from squadron.stats.git_history import GitHistory, GitHistoryError
from squadron.stats.planning_docs import UnknownSliceError
from squadron.stats.producer_report import producer_report
from squadron.stats.producer_units import PHASE_TYPES
from squadron.stats.reviews_report import reviews_usage_report
from squadron.stats.usage_report import RunUsageLoadError, run_usage_report, runs_usage_report

stats_app = typer.Typer(
    name="stats",
    help="Report tokens, turns, time, cost, and planned-versus-actual effort.",
    no_args_is_help=True,
)


@stats_app.command("run")
def stats_run(
    run_id: str = typer.Argument(..., help="The run to report (see `sq runs list --all`)."),
    as_json: bool = typer.Option(False, "--json", help="Emit the rows and totals as JSON."),
) -> None:
    """One row per step action, plus totals."""
    try:
        report = run_usage_report(run_id, StateManager())
    except RunUsageLoadError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    if as_json:
        typer.echo(json.dumps(run_report_json(report), indent=2))
        return
    render_run_report(report, get_console())


@stats_app.command("reviews")
def stats_reviews(
    slice_filter: str | None = typer.Option(
        None, "--slice", help="Only reviews of this slice (index or name)."
    ),
    as_json: bool = typer.Option(False, "--json", help="Emit the rows and totals as JSON."),
) -> None:
    """One row per standalone review artifact, plus totals."""
    reviews_dir = Path.cwd() / REVIEWS_DIR
    report = reviews_usage_report(reviews_dir, slice_filter)
    if as_json:
        typer.echo(json.dumps(reviews_report_json(report), indent=2))
        return
    if report.missing_dir:
        typer.echo(f"No review directory at {reviews_dir}")
        return
    render_reviews_report(report, get_console())


#: The format `--since` takes: the slice design's `dateCreated`.
SINCE_FORMAT = "%Y%m%d"
#: The evidence floor a producer row needs before its cost ratio is shown (D8).
MIN_EVIDENCE_KEY = "metrology.min_evidence_n"


def _fail(message: str) -> typer.Exit:
    typer.echo(f"Error: {message}", err=True)
    return typer.Exit(code=1)


def _loaded_history(project_root: Path) -> GitHistory:
    """The repo's commit graph, loaded; a git failure is an error with exit 1."""
    history = GitHistory(project_root, run=run_git)
    try:
        history.load()
    except GitHistoryError as exc:
        raise _fail(str(exc)) from exc
    return history


@stats_app.command("slice")
def stats_slice(
    index: int = typer.Argument(..., help="The slice index."),
    as_json: bool = typer.Option(False, "--json", help="Emit the report as JSON."),
) -> None:
    """Planned versus actual effort for one slice, with its task groups."""
    project_root = Path.cwd()
    history = _loaded_history(project_root)
    try:
        report = slice_effort_report(
            index, project_root=project_root, history=history, state_manager=StateManager()
        )
    except UnknownSliceError as exc:
        raise _fail(str(exc)) from exc
    if as_json:
        typer.echo(json.dumps(report.to_json_dict(), indent=2))
        return
    render_slice_report(report, get_console())


@stats_app.command("slices")
def stats_slices(
    since: str | None = typer.Option(
        None, "--since", help="Only slices whose design was created on or after YYYYMMDD."
    ),
    as_json: bool = typer.Option(False, "--json", help="Emit the report as JSON."),
) -> None:
    """Completed slices grouped by planned effort: median and range of each actual."""
    if since is not None:
        try:
            datetime.strptime(since, SINCE_FORMAT)
        except ValueError as exc:
            raise _fail(f"--since {since!r} is not a date; expected YYYYMMDD") from exc
    project_root = Path.cwd()
    report = slices_effort_report(
        since=since,
        project_root=project_root,
        history=_loaded_history(project_root),
        state_manager=StateManager(),
    )
    if as_json:
        typer.echo(json.dumps(report.to_json_dict(), indent=2))
        return
    render_slices_report(report, get_console())


def _parse_phase(value: str | None) -> StepTypeName | None:
    """``--phase`` as a phase step type; ``None`` means both phases."""
    if value is None:
        return None
    allowed = [phase.value for phase in PHASE_TYPES]
    if value not in allowed:
        raise _fail(f"--phase {value!r} is not one of: {', '.join(allowed)}")
    return StepTypeName(value)


def _min_evidence_n(project_root: Path) -> int:
    try:
        return get_typed_config(MIN_EVIDENCE_KEY, int, cwd=str(project_root))
    except ValueError as exc:
        raise _fail(f"{exc}. Fix it with 'sq config set {MIN_EVIDENCE_KEY} <n>'.") from exc


@stats_app.command("producers")
def stats_producers(
    phase: str | None = typer.Option(None, "--phase", help="design or tasks; default both."),
    as_json: bool = typer.Option(False, "--json", help="Emit the report as JSON."),
) -> None:
    """Observed producer effectiveness per config, from this machine's pipeline runs."""
    phase_type = _parse_phase(phase)
    report = producer_report(
        phase=phase_type,
        state_manager=StateManager(),
        min_n=_min_evidence_n(Path.cwd()),
    )
    if as_json:
        typer.echo(json.dumps(report.to_json_dict(), indent=2))
        return
    render_producers_report(report, get_console())


@stats_app.command("runs")
def stats_runs(
    slice_index: int | None = typer.Option(None, "--slice", help="Only runs for this slice index."),
    pipeline: str | None = typer.Option(None, "--pipeline", help="Only runs of this pipeline."),
    as_json: bool = typer.Option(False, "--json", help="Emit the rows and totals as JSON."),
) -> None:
    """One row per run, with totals across every matching run."""
    report = runs_usage_report(slice_index=slice_index, pipeline=pipeline, state_manager=StateManager())
    if as_json:
        typer.echo(json.dumps(report.to_json_dict(), indent=2))
        return
    render_runs_report(report, get_console())
