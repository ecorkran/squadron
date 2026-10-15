"""``sq stats``: what runs and reviews spent (slice 175 D8).

Reads only. The cores in ``squadron.stats`` build the reports; this module picks the
input, renders a table or JSON, and maps load errors to exit codes.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich import get_console

from squadron.cli.stats_views import (
    render_reviews_report,
    render_run_report,
    reviews_report_json,
    run_report_json,
)
from squadron.pipeline.state import StateManager
from squadron.review.persistence import REVIEWS_DIR
from squadron.stats.reviews_report import reviews_usage_report
from squadron.stats.usage_report import RunUsageLoadError, run_usage_report

stats_app = typer.Typer(
    name="stats",
    help="Report tokens, turns, time, and cost for runs and reviews.",
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
    if report.missing_dir:
        typer.echo(f"No review directory at {reviews_dir}")
        return
    if as_json:
        typer.echo(json.dumps(reviews_report_json(report), indent=2))
        return
    render_reviews_report(report, get_console())
