"""runs command group — what can I resume? (slice 199)."""

from __future__ import annotations

import typer

from squadron.cli.run_views import render_run_listing
from squadron.pipeline.run_listing import list_run_summaries
from squadron.pipeline.state import StateManager

runs_app = typer.Typer(
    name="runs",
    help="List and wait on pipeline runs.",
    no_args_is_help=True,
)


@runs_app.command("list")
def list_runs(
    include_all: bool = typer.Option(
        False, "--all", help="Include runs with nothing to resume (completed, running)."
    ),
    pipeline: str | None = typer.Option(None, "--pipeline", help="Only runs of this pipeline."),
) -> None:
    """List resumable runs, newest first, with where each one resumes."""
    summaries = list_run_summaries(StateManager(), pipeline=pipeline, include_all=include_all)
    render_run_listing(summaries, include_all=include_all)
