"""pipelines command group — what can I run? (slice 199)."""

from __future__ import annotations

import typer

from squadron.cli.run_views import render_pipeline_listing
from squadron.pipeline.loader import discover_pipelines

pipelines_app = typer.Typer(
    name="pipelines",
    help="List the pipelines available to sq run.",
    no_args_is_help=True,
)


@pipelines_app.command("list")
def list_pipelines() -> None:
    """List effective pipelines grouped by source (built-in, project, user)."""
    render_pipeline_listing(discover_pipelines())
