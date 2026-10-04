"""Branch action — enter or merge a slice's branch (slice 196 D4, D5, D6).

A thin wrapper: the git logic lives in ``pipeline/branch_ops.py``, which the hidden
``sq _branch`` command calls too, so SDK and prompt-only runs do the same thing.
"""

from __future__ import annotations

import asyncio

from squadron.pipeline.actions import ActionType, register_action
from squadron.pipeline.branch_ops import MergeFailedError, enter_slice_branch, merge_slice_branch
from squadron.pipeline.commit_plan import SLICE_PARAM
from squadron.pipeline.git_ops import NoDesignFileError, SliceNotInPlanError, parse_slice_index
from squadron.pipeline.models import ActionContext, ActionResult, ValidationError
from squadron.pipeline.steps.branch import OP_PARAM, BranchOp


class BranchAction:
    """Pipeline action that moves the checkout onto or off a slice's branch."""

    @property
    def action_type(self) -> str:
        return ActionType.BRANCH

    def validate(self, config: dict[str, object]) -> list[ValidationError]:
        """The step type validates ``op``; nothing more is checkable before run time."""
        return []

    async def execute(self, context: ActionContext) -> ActionResult:
        try:
            op = BranchOp(str(context.params.get(OP_PARAM)))
            slice_index = parse_slice_index(context.params.get(SLICE_PARAM))
        except ValueError as exc:
            return self._failure(str(exc))

        try:
            # git and cf run as subprocesses; keep them off the event loop.
            outputs = await asyncio.to_thread(_run_op, op, slice_index, context)
        except (NoDesignFileError, SliceNotInPlanError, MergeFailedError) as exc:
            # This item failed, but the next one may succeed. Environment faults raise
            # past here and end the run.
            return self._failure(str(exc))
        return ActionResult(success=True, action_type=self.action_type, outputs=outputs)

    def _failure(self, error: str) -> ActionResult:
        return ActionResult(success=False, action_type=self.action_type, outputs={}, error=error)


def _run_op(op: BranchOp, slice_index: int, context: ActionContext) -> dict[str, object]:
    match op:
        case BranchOp.ENTER:
            entered = enter_slice_branch(slice_index, context.cwd, context.cf_client)
            return {"branch": entered.branch, "target": entered.target, "created": entered.created}
        case BranchOp.MERGE:
            result = merge_slice_branch(slice_index, context.cwd, context.cf_client)
            return {"branch": result.branch, "target": result.target, "merged": result.outcome}


register_action(ActionType.BRANCH, BranchAction())
