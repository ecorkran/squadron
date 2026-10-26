"""``sq onboard``: report where a project stands on brownfield adoption (slice 440).

The report is read-only and names the next step; ``register``, ``decline`` and
``prompt`` are the only commands that call cf writes or fetch its prompt. The
agent surfaces (``/sq:onboard``, the ``sq-onboard`` Codex skill) loop: run
``sq onboard --json``, do ``next.step``, repeat.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import cast

import typer

from squadron.integrations.cf_adoption import AdoptionClient, CfAdoptionClient
from squadron.integrations.context_forge import ContextForgeError, ContextForgeNotAvailable
from squadron.onboard import build_onboard_report
from squadron.onboard.render import format_report_text

onboard_app = typer.Typer(
    name="onboard",
    help="Report where this project stands on brownfield adoption, and what to do next.",
    invoke_without_command=True,
    no_args_is_help=False,
)

PATH_OPTION_HELP = "Project directory (default: the current directory). Used as given."


def _fail(message: str) -> typer.Exit:
    """Print one line to stderr; the caller raises the returned ``Exit(1)``."""
    typer.echo(message, err=True)
    return typer.Exit(1)


@contextmanager
def cf_errors() -> Iterator[None]:
    """Turn a cf failure into one stderr line and exit 1 (API Contracts, Errors)."""
    try:
        yield
    except (ContextForgeNotAvailable, ContextForgeError) as exc:
        raise _fail(str(exc)) from exc


def resolve_root(path: Path | None) -> Path:
    """The directory to judge: *path* (or the cwd), resolved, never widened (D4)."""
    root = (path if path is not None else Path.cwd()).resolve()
    if not root.is_dir():
        raise _fail(f"--path is not an existing directory: {root}")
    return root


def get_client(ctx: typer.Context) -> AdoptionClient:
    """The adoption client the callback put on ``ctx.obj`` (tests inject a fake there)."""
    return cast("AdoptionClient", ctx.obj)


@onboard_app.callback()
def onboard(
    ctx: typer.Context,
    path: Path | None = typer.Option(None, "--path", help=PATH_OPTION_HELP),
    as_json: bool = typer.Option(False, "--json", help="Print the report as JSON."),
) -> None:
    """With no subcommand, print the adoption report for ``--path``."""
    if ctx.obj is None:
        ctx.obj = CfAdoptionClient.from_config()
    if ctx.invoked_subcommand is not None:
        if path is not None or as_json:
            raise _fail(
                f"pass options after the subcommand: sq onboard {ctx.invoked_subcommand} --path DIR"
            )
        return
    root = resolve_root(path)
    with cf_errors():
        report = build_onboard_report(root, get_client(ctx))
    typer.echo(json.dumps(report.to_json(), indent=2) if as_json else format_report_text(report))
