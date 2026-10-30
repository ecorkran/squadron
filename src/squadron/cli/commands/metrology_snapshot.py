"""``sq metrology snapshot`` (slice 400).

A thin Typer shell over ``squadron.metrology.snapshot``, kept in its own module and
mounted onto ``metrology_app`` by the parent (the ``audit delta`` pattern).
"""

from __future__ import annotations

import logging
from pathlib import Path

import typer

from squadron.metrology.errors import (
    MetrologyIdentityError,
    MetrologyStoreError,
    SnapshotAdapterContractError,
    SnapshotExportError,
    SnapshotIntegrityError,
    SnapshotPreflightError,
)
from squadron.metrology.snapshot.registry import default_registry
from squadron.metrology.snapshot.render import render_summary
from squadron.metrology.snapshot.runner import SubprocessToolRunner
from squadron.metrology.snapshot.take import take_snapshot, take_snapshot_at
from squadron.metrology.store import MetrologyStore, resolve_store_dir

_logger = logging.getLogger(__name__)

#: Failures a snapshot-taking command reports on stderr and turns into exit 1.
SNAPSHOT_FAILURES = (
    SnapshotPreflightError,
    SnapshotIntegrityError,
    SnapshotAdapterContractError,
    SnapshotExportError,
    MetrologyIdentityError,
)


def register_snapshot_command(metrology_app: typer.Typer) -> None:
    """Mount ``snapshot`` onto the parent module's existing metrology app."""

    @metrology_app.command("snapshot")
    def snapshot(  # pyright: ignore[reportUnusedFunction]
        cwd: str | None = typer.Option(
            None, "--cwd", help="Repository root to measure (default: the current directory)"
        ),
        as_json: bool = typer.Option(
            False, "--json", help="Print the CodeSnapshot record as JSON instead of a summary"
        ),
        commit: str | None = typer.Option(
            None,
            "--commit",
            metavar="REV",
            help="Measure this commit from a temp export instead of the clean HEAD",
        ),
    ) -> None:
        """Measure the clean HEAD of a repository and record one code snapshot.

        With --commit REV, any commit is measured from a temp export using this
        checkout's tools and settings; the checkout's state doesn't matter and
        nothing is written into it.

        Writes one record per commit to the metrology store: file length, function
        length, lint count and type-error count for each language that has an
        adapter. A metric that can't be measured is recorded as absent with a reason.
        The tree must be clean (an untracked .squadron.toml is allowed). Nothing is
        written into the repository.

        Security: snapshotting a repository runs executables and config taken from
        that repository: its .venv/bin/ruff, .venv/bin/pyright and .venv/bin/python,
        node_modules/.bin/eslint and its JavaScript config. That executes the
        repository's code, with your full environment (including any secrets in it)
        inherited. Only snapshot repositories you trust.
        """
        repo_root = Path(cwd).expanduser().resolve() if cwd else Path.cwd().resolve()
        store_dir = resolve_store_dir(cwd=str(repo_root))
        try:
            store = MetrologyStore(store_dir=store_dir)
            if commit is None:
                taken = take_snapshot(repo_root, default_registry(), SubprocessToolRunner(), store)
            else:
                taken = take_snapshot_at(
                    repo_root, commit, default_registry(), SubprocessToolRunner(), store
                )
        except SNAPSHOT_FAILURES as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(code=1) from exc
        except MetrologyStoreError as exc:
            _logger.error("Could not write the code snapshot to %s: %s", store_dir, exc)
            typer.echo(f"Store error: {exc}", err=True)
            raise typer.Exit(code=1) from exc
        if as_json:
            typer.echo(taken.model_dump_json(indent=2))
            return
        record_path = store.record_location(taken.snapshot_id)
        for line in render_summary(taken, record_path, exported=commit is not None):
            typer.echo(line)
