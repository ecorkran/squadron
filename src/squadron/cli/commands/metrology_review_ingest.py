"""``sq metrology ingest-reviews`` (slice 402).

A thin Typer shell over ``squadron.metrology.review_ingest``, kept in its own module and
mounted onto ``metrology_app`` by the parent (the ``snapshot`` pattern).
"""

from __future__ import annotations

import logging
from pathlib import Path

import typer

from squadron.metrology.errors import (
    MetrologyIdentityError,
    MetrologyStoreError,
    ReviewIngestInputError,
)
from squadron.metrology.identity import derive_project_id
from squadron.metrology.review_ingest import IngestResult, ingest_reviews, resolve_review_files
from squadron.metrology.store import MetrologyStore, resolve_store_dir

_logger = logging.getLogger(__name__)

_INPUT_FAILURES = (MetrologyIdentityError, ReviewIngestInputError)


def _echo_summary(result: IngestResult, store_dir: Path) -> None:
    typer.echo(f"Ingested {result.ingested} code reviews into {store_dir} ({result.replaced} replaced)")
    typer.echo(
        f"Skipped: {result.skipped_not_code} not code reviews, "
        f"{result.skipped_unknown_verdict} unknown verdict"
    )
    typer.echo(f"Failed: {len(result.failed)}")
    for path, reason in result.failed:
        typer.echo(f"  {path}: {reason}")


def register_review_ingest_command(metrology_app: typer.Typer) -> None:
    """Mount ``ingest-reviews`` onto the parent module's existing metrology app."""

    @metrology_app.command("ingest-reviews")
    def ingest_reviews_command(  # pyright: ignore[reportUnusedFunction]
        paths: list[Path] | None = typer.Argument(
            None,
            help="Review files or directories (default: the project's reviews directory)",
        ),
        cwd: str | None = typer.Option(
            None, "--cwd", help="Project root (default: the current directory)"
        ),
    ) -> None:
        """Write one code_review record per code-review file into the metrology store.

        Re-running is safe: a record is keyed on project and path, so ingesting a file
        again replaces its record. Arch, slice and tasks reviews and reviews with an
        UNKNOWN verdict are skipped and counted. Reviews written before categories were
        normalized are mapped through a fixed table and marked read-side mapped.
        """
        repo_root = Path(cwd).expanduser().resolve() if cwd else Path.cwd().resolve()
        store_dir = resolve_store_dir(cwd=str(repo_root))
        result = IngestResult()
        try:
            project_id = derive_project_id(str(repo_root))
            files, directories = resolve_review_files(paths or [], project_id, repo_root)
            if not files:
                searched = ", ".join(str(directory) for directory in directories)
                _logger.warning("No review files (*.md) found in %s", searched)
            ingest_reviews(project_id, repo_root, files, MetrologyStore(store_dir=store_dir), result)
        except _INPUT_FAILURES as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(code=1) from exc
        except MetrologyStoreError as exc:
            _logger.error("Could not write a code review to %s: %s", store_dir, exc)
            _echo_summary(result, store_dir)
            typer.echo(f"Store error: {exc}", err=True)
            raise typer.Exit(code=1) from exc
        _echo_summary(result, store_dir)
        if result.failed:
            raise typer.Exit(code=1)
