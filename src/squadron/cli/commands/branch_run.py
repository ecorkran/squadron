"""[hidden] Enter or merge a slice's branch (slice 196 D4).

Used by prompt-only pipeline rendering: the harness runs this where the SDK executor
would run ``BranchAction``. The action does the work, so both modes make the same git
moves and refuse the same misplaced checkouts.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

import typer

from squadron.integrations.context_forge import ContextForgeClient, ContextForgeError
from squadron.pipeline.actions.branch import BranchAction
from squadron.pipeline.commit_plan import SLICE_PARAM
from squadron.pipeline.git_ops import GitEnvironmentError
from squadron.pipeline.models import ActionContext
from squadron.pipeline.resolver import ModelResolver
from squadron.pipeline.steps.branch import OP_PARAM, BranchOp

_logger = logging.getLogger(__name__)


def branch_run(
    op: BranchOp = typer.Argument(..., help="enter or merge."),
    slice_index: int = typer.Option(..., "--slice", help="Slice index."),
) -> None:
    """[hidden] Enter or merge the slice branch for ``--slice``."""
    context = ActionContext(
        pipeline_name="_branch",
        run_id="",
        params={OP_PARAM: op.value, SLICE_PARAM: str(slice_index)},
        step_name="_branch",
        step_index=0,
        prior_outputs={},
        resolver=ModelResolver(),
        cf_client=ContextForgeClient(),
        cwd=os.getcwd(),
    )
    try:
        result = asyncio.run(BranchAction().execute(context))
    except (GitEnvironmentError, ContextForgeError) as exc:
        # CLI process boundary: an environment failure ends the run, with the same
        # text the SDK executor would raise.
        _logger.exception("_branch: environment failure")
        print(f"Error: {exc}", file=sys.stderr)
        raise typer.Exit(code=1) from None

    if not result.success:
        print(f"Error: {result.error}", file=sys.stderr)
        raise typer.Exit(code=1)
    print(_describe(op, result.outputs))


def _describe(op: BranchOp, outputs: dict[str, object]) -> str:
    """What the action did, for the harness to read."""
    match op:
        case BranchOp.ENTER:
            origin = f"created from {outputs['target']}" if outputs["created"] else "existing"
            return f"on {outputs['branch']} ({origin})"
        case BranchOp.MERGE:
            return f"{outputs['merged']} {outputs['branch']} into {outputs['target']}"
