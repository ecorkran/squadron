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
from typing import Annotated, cast

import typer

from squadron.integrations.cf_adoption import (
    STEP_STATUS_FAILED,
    WORKTREE_ERROR_CODE,
    AdoptionClient,
    CfAdoptionClient,
    ContextForgeReportError,
    InitReport,
)
from squadron.integrations.context_forge import ContextForgeError, ContextForgeNotAvailable
from squadron.onboard import build_onboard_report
from squadron.onboard.comprehension import newest_comprehension
from squadron.onboard.render import format_report_text

onboard_app = typer.Typer(
    name="onboard",
    help="Report where this project stands on brownfield adoption, and what to do next.",
    invoke_without_command=True,
    no_args_is_help=False,
)

PathOption = Annotated[
    Path | None,
    typer.Option("--path", help="Project directory (default: the current directory). Used as given."),
]

NO_COMPREHENSION_MESSAGE = "No comprehension doc; run the comprehension step first"
WORKTREE_GUIDANCE = (
    "Run `cf worktree init` in this directory, or run `sq onboard` in the primary checkout."
)


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
    path: PathOption = None,
    as_json: Annotated[bool, typer.Option("--json", help="Print the report as JSON.")] = False,
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


def _print_init_report(report: InitReport) -> None:
    typer.echo(f"Project: {report.project_name} ({report.registration})")
    for step in report.steps:
        detail = f" - {step.message}" if step.message else ""
        typer.echo(f"  {step.step}: {step.status}{detail}")
    for notice in report.notices:
        typer.echo(f"Notice: {notice}")


@onboard_app.command()
def register(
    ctx: typer.Context,
    path: PathOption = None,
    ide: Annotated[
        str | None,
        typer.Option("--ide", help="IDE target for cf init, passed to cf unvalidated."),
    ] = None,
) -> None:
    """Register the project with cf (``cf init``); safe to re-run after a failure."""
    root = resolve_root(path)
    with cf_errors():
        try:
            report = get_client(ctx).init_project(root, ide)
        except ContextForgeReportError as exc:
            if exc.code != WORKTREE_ERROR_CODE:
                raise
            typer.echo(exc.message, err=True)
            raise _fail(WORKTREE_GUIDANCE) from exc
    _print_init_report(report)
    if not report.ok:
        failed = [step.step for step in report.steps if step.status == STEP_STATUS_FAILED]
        raise _fail(f"cf init failed steps: {', '.join(failed) or 'none named'}")


@onboard_app.command()
def decline(ctx: typer.Context, path: PathOption = None) -> None:
    """Opt this project out of brownfield adoption."""
    root = resolve_root(path)
    with cf_errors():
        get_client(ctx).decline(root)
    typer.echo(f"Opted out of brownfield adoption for {root}; /cf:onboard now treats it as new.")


@onboard_app.command()
def prompt(ctx: typer.Context, path: PathOption = None) -> None:
    """Print cf's adoption prompt, built from the newest comprehension doc."""
    root = resolve_root(path)
    comprehension = newest_comprehension(root)
    if comprehension is None:
        raise _fail(NO_COMPREHENSION_MESSAGE)
    with cf_errors():
        text = get_client(ctx).adoption_prompt(root, comprehension)
    typer.echo(text, nl=False)
