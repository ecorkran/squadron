"""pipelines command group — what can I run? (slice 199)."""

from __future__ import annotations

import logging
import sys

import typer

from squadron.cli.run_views import render_pipeline_listing
from squadron.pipeline.loader import discover_pipelines, resolve_pipeline

_logger = logging.getLogger(__name__)

pipelines_app = typer.Typer(
    name="pipelines",
    help="List and show the pipelines available to sq run.",
    no_args_is_help=True,
)


@pipelines_app.command("list")
def list_pipelines(
    verbose: bool = typer.Option(
        False, "-v", "--verbose", help="Add each pipeline's first params and their defaults."
    ),
) -> None:
    """List effective pipelines grouped by source (built-in, project, user)."""
    render_pipeline_listing(discover_pipelines(), verbose=verbose)


@pipelines_app.command("show")
def show_pipeline(
    name: str = typer.Argument(..., help="Pipeline name, as sq run takes it."),
    path_only: bool = typer.Option(False, "--path", help="Print only the file's path."),
) -> None:
    """Print the YAML a pipeline name runs, with its source and path as comments."""
    try:
        location = resolve_pipeline(name)
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from None
    if path_only:
        typer.echo(str(location.path))
        return
    try:
        # Read whole before printing anything, so a failed read leaves stdout empty.
        content = location.path.read_bytes()
    except OSError as exc:
        _logger.error("pipelines show: cannot read %s: %s", location.path, exc)
        typer.echo(f"Error: cannot read {location.path}: {exc.strerror or exc}", err=True)
        raise typer.Exit(1) from None
    header = f"# source: {location.source}\n# path: {location.path}\n"
    sys.stdout.buffer.write(header.encode() + content)
    sys.stdout.buffer.flush()
