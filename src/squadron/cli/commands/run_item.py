"""``sq run --resume <run_id> --item <index> --decision retry|accept`` (slice 197 D8).

Builds the request, hands ``resume_item`` a body runner that runs the pipeline the
same way a fresh ``sq run`` does, prints the new record and the report path, and exits
with the ``ResumeExit`` code.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from collections.abc import Awaitable, Callable

import typer
from rich import print as rprint
from rich.markup import escape

from squadron.integrations.context_forge import ContextForgeClient
from squadron.pipeline.batch_report import ItemDecision, ItemRerun
from squadron.pipeline.item_resume import (
    ResumeExit,
    ResumeOutcome,
    ResumeRequest,
    resume_item,
)
from squadron.pipeline.state import StateManager

_logger = logging.getLogger(__name__)

# Exit code for a refused combination of flags: Typer's usage error, "nothing ran".
USAGE_EXIT = int(ResumeExit.REJECTED)


def check_item_flags(
    resume: str | None,
    item: str | None,
    decision: ItemDecision | None,
    instructions: str | None,
) -> None:
    """Refuse a combination of item-resume flags that cannot mean anything."""
    problem: str | None = None
    if item is None and (decision is not None or instructions is not None):
        problem = "--decision and --instructions require --item"
    elif item is not None and resume is None:
        problem = "--item requires --resume <run_id>"
    elif item is not None and decision is None:
        problem = "--item requires --decision retry|accept"
    if problem is not None:
        rprint(f"[red]Error: {escape(str(problem))}.[/red]", file=sys.stderr)
        raise typer.Exit(USAGE_EXIT)


def handle_item_resume(
    run_id: str,
    item: str,
    decision: ItemDecision,
    instructions: str | None,
    model: str | None,
    overrides: dict[str, object],
    strict: bool,
    run_pipeline_sdk: Callable[..., Awaitable[object]],
) -> None:
    """Run the item resume and exit with its ``ResumeExit`` code.

    ``run_pipeline_sdk`` is the runner a fresh ``sq run`` uses, so the item's body
    runs exactly as it would in the batch.
    """
    request = ResumeRequest(
        run_id=run_id,
        index=item,
        decision=decision,
        instructions=instructions,
        model=model,
        param_overrides=overrides,
    )

    async def run_body(pipeline: str, params: dict[str, object], rerun: ItemRerun) -> object:
        return await run_pipeline_sdk(
            pipeline,
            params,
            model_override=model,
            run_id=run_id,
            from_step=rerun.report.step_name,
            strict=strict,
            item_rerun=rerun,
        )

    try:
        outcome = asyncio.run(
            resume_item(
                request,
                cwd=os.getcwd(),
                cf_client=ContextForgeClient(),
                state_manager=StateManager(),
                run_body=run_body,
            )
        )
    except typer.Exit as exc:
        # The pipeline runner refused mid-item (classification, lost session); it has
        # printed why. The item did not finish.
        _logger.error(
            "item resume %s item %s halted: pipeline runner exited %s", run_id, item, exc.exit_code
        )
        rprint(f"[red]Item {escape(item)} did not finish (exit {escape(str(exc.exit_code))}).[/red]")
        raise typer.Exit(int(ResumeExit.HALTED)) from None
    _print(outcome)
    raise typer.Exit(int(outcome.exit))


def _print(outcome: ResumeOutcome) -> None:
    color = "green" if outcome.exit is ResumeExit.RESOLVED else "yellow"
    if outcome.exit in (ResumeExit.REJECTED, ResumeExit.HALTED):
        color = "red"
    rprint(f"[{color}]{outcome.exit.name}[/{color}] {escape(outcome.message)}")
    if outcome.report_path is not None:
        rprint(f"  Report: {escape(str(outcome.report_path))}")
