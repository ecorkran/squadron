"""Helpers shared by the ``sq benchmark`` commands."""

from __future__ import annotations

from pathlib import Path

import typer

from squadron.codehost.git_refs import GIT_QUERY_TIMEOUT_SECONDS
from squadron.core.process_runner import ProcessRunner
from squadron.metrology.benchmark_store import BenchmarkRecordStore
from squadron.metrology.errors import MetrologyStoreError
from squadron.metrology.store import MetrologyStore, resolve_store_dir


def stderr_exit(message: str) -> typer.Exit:
    """Print an error to stderr and return the exit to raise: ``raise stderr_exit("...")``."""
    typer.echo(message, err=True)
    return typer.Exit(1)


def git_output(runner: ProcessRunner, repo_root: str, *args: str) -> str:
    """Stdout of ``git -C repo_root ARGS``, or a stderr exit with git's message."""
    result = runner.run(["git", "-C", repo_root, *args], cwd=None, timeout=GIT_QUERY_TIMEOUT_SECONDS)
    if result.returncode != 0:
        raise stderr_exit(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def repo_root_for(runner: ProcessRunner, repo: Path | None) -> Path:
    """The git toplevel of *repo*, or of the current directory when ``None``."""
    start = str(repo if repo is not None else Path.cwd())
    return Path(git_output(runner, start, "rev-parse", "--show-toplevel"))


def open_store(repo_root: Path) -> BenchmarkRecordStore:
    """The benchmark record store configured for *repo_root*, or a stderr exit."""
    try:
        return BenchmarkRecordStore(MetrologyStore(store_dir=resolve_store_dir(cwd=str(repo_root))))
    except MetrologyStoreError as exc:
        raise stderr_exit(str(exc)) from exc
