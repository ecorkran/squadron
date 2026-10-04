"""Branch action — enter or merge a slice's branch (slice 196 D4, D5, D6).

A thin wrapper: the git logic lives in ``pipeline/branch_ops.py``, which the hidden
``sq _branch`` command calls too, so SDK and prompt-only runs do the same thing.
"""

from __future__ import annotations

from squadron.pipeline.actions import ActionType, register_action
from squadron.pipeline.branch_ops import enter_slice_branch, merge_slice_branch
from squadron.pipeline.git_ops import parse_slice_index
from squadron.pipeline.models import ActionContext, ActionResult, ValidationError
from squadron.pipeline.steps.branch import BranchOp


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
            op = BranchOp(str(context.params.get("op")))
            slice_index = parse_slice_index(context.params.get("slice"))
        except ValueError as exc:
            return self._failure(str(exc))

        try:
            match op:
                case BranchOp.ENTER:
                    entered = enter_slice_branch(slice_index, context.cwd, context.cf_client)
                    outputs: dict[str, object] = {
                        "branch": entered.branch,
                        "target": entered.target,
                        "created": entered.created,
                    }
                case BranchOp.MERGE:
                    result = merge_slice_branch(slice_index, context.cwd, context.cf_client)
                    outputs = {
                        "branch": result.branch,
                        "target": result.target,
                        "merged": result.outcome,
                    }
        except ValueError as exc:
            # No design file, the slice is not in the plan, or a merge that was aborted back
            # to a clean target: this item failed, but the next one may succeed. Environment
            # faults raise past here and end the run.
            return self._failure(str(exc))
        return ActionResult(success=True, action_type=self.action_type, outputs=outputs)

    def _failure(self, error: str) -> ActionResult:
        return ActionResult(success=False, action_type=self.action_type, outputs={}, error=error)


register_action(ActionType.BRANCH, BranchAction())
