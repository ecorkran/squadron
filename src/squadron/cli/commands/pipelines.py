"""pipelines command group — what can I run? (slice 199)."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import typer

from squadron.cli.run_views import render_pipeline_listing
from squadron.core.file_write import write_new_file
from squadron.pipeline.loader import (
    PipelineScope,
    discover_pipelines,
    pipeline_target_dir,
    resolve_pipeline,
)

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


@pipelines_app.command("copy")
def copy_pipeline(
    name: str = typer.Argument(..., help="Pipeline name, as sq run takes it."),
    new_name: str | None = typer.Argument(
        None, help="Name for the copy. Omitted, the copy keeps the name and shadows the original."
    ),
    project: bool = typer.Option(
        False, "--project", help="Write to this project's pipelines directory, not the user's."
    ),
    force: bool = typer.Option(False, "--force", help="Replace an existing file."),
) -> None:
    """Copy a pipeline's YAML into your pipelines directory so you can edit it."""
    try:
        location = resolve_pipeline(name)
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from None
    copy_name = new_name or location.name
    if Path(copy_name).name != copy_name:
        typer.echo(f"Error: '{copy_name}' is not a plain pipeline name.", err=True)
        raise typer.Exit(1)
    scope = PipelineScope.PROJECT if project else PipelineScope.USER
    target = pipeline_target_dir(scope) / f"{copy_name}.yaml"
    if target.resolve() == location.path.resolve():
        typer.echo(f"Error: {target} is the pipeline's own file; nothing to copy.", err=True)
        raise typer.Exit(1)
    try:
        # Read whole before writing, so a failed read leaves the target alone.
        content = location.path.read_bytes()
    except OSError as exc:
        _logger.error("pipelines copy: cannot read %s: %s", location.path, exc)
        typer.echo(f"Error: cannot read {location.path}: {exc.strerror or exc}", err=True)
        raise typer.Exit(1) from None
    try:
        write_new_file(target, content, force=force)
    except FileExistsError:
        typer.echo(f"Error: {target} already exists; use --force to replace it.", err=True)
        raise typer.Exit(1) from None
    except OSError as exc:
        _logger.error("pipelines copy: cannot write %s: %s", target, exc)
        typer.echo(f"Error: cannot write {target}: {exc.strerror or exc}", err=True)
        raise typer.Exit(1) from None
    typer.echo(str(target))
    if new_name is None:
        typer.echo(
            f"Note: this copy now shadows the {location.source} pipeline '{location.name}'.", err=True
        )
