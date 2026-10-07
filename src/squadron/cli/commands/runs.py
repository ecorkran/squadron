"""runs command group — what can I resume, and is it done yet? (slice 199)."""

from __future__ import annotations

import typer

from squadron.cli.run_views import (
    render_run_listing,
    render_run_status,
    unavailable_details,
    unavailable_summary,
)
from squadron.pipeline.run_listing import list_run_summaries
from squadron.pipeline.run_wait import WAIT_EXIT_CODES, WaitOutcome, orphaned_message, wait_for_run
from squadron.pipeline.state import StateManager

runs_app = typer.Typer(
    name="runs",
    help="List and wait on pipeline runs.",
    no_args_is_help=True,
)


@runs_app.command("list")
def list_runs(
    include_all: bool = typer.Option(
        False, "--all", help="Include completed runs with nothing to resume."
    ),
    pipeline: str | None = typer.Option(None, "--pipeline", help="Only runs of this pipeline."),
    verbose: bool = typer.Option(
        False, "-v", "--verbose", help="Name each unavailable pipeline and why it failed to load."
    ),
) -> None:
    """List running and resumable runs, newest first: where each is, or where it resumes."""
    listing = list_run_summaries(StateManager(), pipeline=pipeline, include_all=include_all)
    render_run_listing(listing.rows, include_all=include_all)
    if listing.unavailable:
        typer.echo(unavailable_summary(listing), err=True)
        if verbose:
            for line in unavailable_details(listing):
                typer.echo(line, err=True)


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
        "An orphaned run ends the wait; a stale one (heartbeat overdue, process "
        "not provably gone) keeps waiting, so this is the bound for that case.",
    ),
) -> None:
    state_manager = StateManager()
    result = wait_for_run(state_manager, run_id, timeout=timeout)
    outcome = result.outcome
    if outcome in _STATUS_PANEL_OUTCOMES and result.state is not None:
        render_run_status(result.state)
    code = WAIT_EXIT_CODES[outcome]
    if outcome is WaitOutcome.ORPHANED:
        typer.echo(orphaned_message(run_id, result.state), err=True)
    elif code != 0:
        typer.echo(f"sq runs wait: run {run_id} {outcome}", err=True)
    raise typer.Exit(code)
