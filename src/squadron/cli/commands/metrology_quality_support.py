"""Shared setup for the quality commands (slice 403): context, error handling, git probes."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import typer

from squadron.cli.commands.metrology_snapshot import SNAPSHOT_FAILURES
from squadron.metrology.errors import MetrologyStoreError
from squadron.metrology.identity import derive_project_id
from squadron.metrology.models import ProjectId
from squadron.metrology.snapshot.registry import default_registry
from squadron.metrology.snapshot.runner import SubprocessToolRunner
from squadron.metrology.snapshot.take import take_snapshot_at
from squadron.metrology.snapshot_models import CodeSnapshot
from squadron.metrology.store import MetrologyStore, resolve_store_dir
from squadron.review.git_utils import resolve_diff_base, run_git

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class QualityContext:
    """What every quality command needs: the repo, its project, the store and the target."""

    repo_root: Path
    project_id: ProjectId
    store: MetrologyStore
    target: str


@contextmanager
def exit_on_failure() -> Iterator[None]:
    """Turn a known failure into a stderr message and exit 1; anything else propagates."""
    try:
        yield
    except SNAPSHOT_FAILURES as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except MetrologyStoreError as exc:
        _logger.error("Metrology store failure: %s", exc)
        typer.echo(f"Store error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


def load_context(cwd: str | None) -> QualityContext:
    """Resolve the repo root, project identity, store and target branch for a command."""
    repo_root = Path(cwd).expanduser().resolve() if cwd else Path.cwd().resolve()
    return QualityContext(
        repo_root=repo_root,
        project_id=derive_project_id(str(repo_root)),
        store=MetrologyStore(store_dir=resolve_store_dir(cwd=str(repo_root))),
        target=resolve_diff_base(str(repo_root)),
    )


def take_commit(repo_root: Path, commit: str, store: MetrologyStore) -> CodeSnapshot:
    """Measure *commit* from a temp export with the default adapters."""
    return take_snapshot_at(repo_root, commit, default_registry(), SubprocessToolRunner(), store)


def commit_exists(repo_root: Path, sha: str) -> bool:
    """Whether *sha* names a commit in the repo; a git call that can't answer exits 1."""
    call = f"git cat-file -e {sha}^{{commit}}"
    completed = run_git(["cat-file", "-e", f"{sha}^{{commit}}"], cwd=str(repo_root))
    if completed is None:
        _logger.error("%s returned no result in %s", call, repo_root)
        typer.echo(f"Error: `{call}` could not be run in {repo_root}.", err=True)
        raise typer.Exit(code=1)
    return completed.returncode == 0


def first_parent_history(repo_root: Path, target: str) -> list[str]:
    """The target's first-parent commits, oldest first; a failing git call exits 1."""
    call = f"git rev-list --first-parent --reverse {target}"
    completed = run_git(["rev-list", "--first-parent", "--reverse", target], cwd=str(repo_root))
    if completed is None or completed.returncode != 0:
        _logger.error("%s failed in %s", call, repo_root)
        typer.echo(f"Error: `{call}` failed in {repo_root}.", err=True)
        raise typer.Exit(code=1)
    return completed.stdout.split()
