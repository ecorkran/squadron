"""Helpers shared by the ``sq benchmark`` commands."""

from __future__ import annotations

import typer

from squadron.core.process_runner import ProcessRunner

GIT_TIMEOUT_S = 60


def stderr_exit(message: str) -> typer.Exit:
    """Print an error to stderr and return the exit to raise: ``raise stderr_exit("...")``."""
    typer.echo(message, err=True)
    return typer.Exit(1)


def git_output(runner: ProcessRunner, repo_root: str, *args: str) -> str:
    """Stdout of ``git -C repo_root ARGS``, or a stderr exit with git's message."""
    result = runner.run(["git", "-C", repo_root, *args], cwd=None, timeout=GIT_TIMEOUT_S)
    if result.returncode != 0:
        raise stderr_exit(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()
