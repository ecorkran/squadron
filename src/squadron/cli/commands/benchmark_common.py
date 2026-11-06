"""Helpers shared by the ``sq benchmark`` commands."""

from __future__ import annotations

import typer


def stderr_exit(message: str) -> typer.Exit:
    """Print an error to stderr and return the exit to raise: ``raise stderr_exit("...")``."""
    typer.echo(message, err=True)
    return typer.Exit(1)
