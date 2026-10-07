"""runs command group — what can I resume, and is it done yet? (slice 199)."""

from __future__ import annotations

import typer

from squadron.cli.run_views import render_run_listing, render_run_status
from squadron.pipeline.run_listing import list_run_summaries
from squadron.pipeline.run_wait import WAIT_EXIT_CODES, WaitOutcome, wait_for_run
from squadron.pipeline.state import StateManager

runs_app = typer.Typer(
    name="runs",
    help="List and wait on pipeline runs.",
    no_args_is_help=True,
)


@runs_app.command("list")
def list_runs(
    include_all: bool = typer.Option(
        False, "--all", help="Include runs with nothing to resume (completed, running)."
    ),
    pipeline: str | None = typer.Option(None, "--pipeline", help="Only runs of this pipeline."),
) -> None:
    """List resumable runs, newest first, with where each one resumes."""
    summaries = list_run_summaries(StateManager(), pipeline=pipeline, include_all=include_all)
    render_run_listing(summaries, include_all=include_all)


# Outcomes where the run left `running` and its state is readable, so its panel prints.
_STATUS_PANEL_OUTCOMES = frozenset(
    {WaitOutcome.COMPLETED, WaitOutcome.FAILED, WaitOutcome.PAUSED, WaitOutcome.UNKNOWN_STATUS}
)


_WAIT_HELP = "Block until a run leaves 'running', then print its status.\n\nExit codes: " + ", ".join(
    f"{code} {outcome}" for outcome, code in WAIT_EXIT_CODES.items()
)


@runs_app.command("wait", help=_WAIT_HELP)
def wait(
    run_id: str = typer.Argument(..., help="The run to wait on."),
    timeout: float | None = typer.Option(
        None,
        "--timeout",
        min=0.0,
        help=f"Give up after SECONDS (exit {WAIT_EXIT_CODES[WaitOutcome.TIMED_OUT]}). "
        "A crashed run stays 'running' forever, so this is the only bound; "
        "without it the wait never ends on its own.",
    ),
) -> None:
    state_manager = StateManager()
    result = wait_for_run(state_manager, run_id, timeout=timeout)
    outcome = result.outcome
    if outcome in _STATUS_PANEL_OUTCOMES and result.state is not None:
        render_run_status(result.state)
    code = WAIT_EXIT_CODES[outcome]
    if code != 0:
        typer.echo(f"sq runs wait: run {run_id} {outcome}", err=True)
    raise typer.Exit(code)
