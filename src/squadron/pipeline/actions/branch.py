"""Branch action — enter or merge a slice's branch (slice 196 D4, D5, D6).

A thin wrapper: the git logic lives in ``pipeline/branch_ops.py``, which the hidden
``sq _branch`` command calls too, so SDK and prompt-only runs do the same thing.
"""

from __future__ import annotations

import asyncio
import logging

from squadron.pipeline.actions import ActionType, register_action
from squadron.pipeline.branch_ops import (
    BRANCH_OUTPUT,
    FAILURE_OUTPUT,
    MERGED_OUTPUT,
    SKIPPED_OUTPUT,
    TARGET_OUTPUT,
    BranchFailure,
    MergeFailedError,
    enter_slice_branch,
    merge_slice_branch,
)
from squadron.pipeline.commit_plan import SLICE_PARAM
from squadron.pipeline.git_ops import NoDesignFileError, SliceNotInPlanError, parse_slice_index
from squadron.pipeline.models import ActionContext, ActionResult, ValidationError
from squadron.pipeline.steps.branch import OP_PARAM, WHEN_PARAM, BranchOp

_logger = logging.getLogger(__name__)
_WHEN_VALUES = {"true": True, "false": False}


def parse_when(value: object) -> bool:
    """Whether a branch op runs: absent means yes; otherwise ``true`` or ``false``.

    Raises ValueError for anything else, including an unresolved ``{param}``.
    """
    if value is None or isinstance(value, bool):
        return value is not False
    enabled = _WHEN_VALUES.get(str(value).strip().lower())
    if enabled is None:
        raise ValueError(f"branch '{WHEN_PARAM}' must be true or false, got {value!r}")
    return enabled


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
            enabled = parse_when(context.params.get(WHEN_PARAM))
        except ValueError as exc:
            return self._failure(str(exc))
        if not enabled:
            _logger.info("branch %s for slice %d skipped: when is false", op, slice_index)
            return ActionResult(
                success=True, action_type=self.action_type, outputs={SKIPPED_OUTPUT: True}
            )

        try:
            # git and cf run as subprocesses; keep them off the event loop.
            outputs = await asyncio.to_thread(_run_op, op, slice_index, context)
        except MergeFailedError as exc:
            return self._failure(str(exc), exc.failure)
        except (NoDesignFileError, SliceNotInPlanError) as exc:
            # This item failed, but the next one may succeed. Environment faults raise
            # past here and end the run.
            return self._failure(str(exc))
        return ActionResult(success=True, action_type=self.action_type, outputs=outputs)

    def _failure(self, error: str, failure: BranchFailure = BranchFailure.OTHER) -> ActionResult:
        """An item failure, classified so the flag kind is set without reading ``error``."""
        return ActionResult(
            success=False,
            action_type=self.action_type,
            outputs={FAILURE_OUTPUT: failure},
            error=error,
            # Unfinished work waits on a person; it is not broken (D6).
            awaits_human=failure is BranchFailure.UNFINISHED_TASKS,
        )


def _run_op(op: BranchOp, slice_index: int, context: ActionContext) -> dict[str, object]:
    match op:
        case BranchOp.ENTER:
            entered = enter_slice_branch(slice_index, context.cwd, context.cf_client)
            return {
                BRANCH_OUTPUT: entered.branch,
                TARGET_OUTPUT: entered.target,
                "created": entered.created,
            }
        case BranchOp.MERGE:
            result = merge_slice_branch(slice_index, context.cwd, context.cf_client)
            return {
                BRANCH_OUTPUT: result.branch,
                TARGET_OUTPUT: result.target,
                MERGED_OUTPUT: result.outcome,
            }


register_action(ActionType.BRANCH, BranchAction())
