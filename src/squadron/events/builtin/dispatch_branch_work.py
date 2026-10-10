"""squadron.dispatch-branch-work — POST_ACTION check that an implement dispatch
left commits on the slice branch.

The implement counterpart of squadron.dispatch-artifact: an agent that stops to
ask the Project Manager writes no code, and the review that follows would run
against an empty branch. Failing here ends the step with the agent's own words.
"""

from __future__ import annotations

import asyncio
import logging

from squadron.events import EventType, register_event_action
from squadron.events.contexts import EventContext, PostActionContext
from squadron.pipeline.actions.dispatch import SKIPPED_KEY
from squadron.pipeline.branch_ops import slice_facts
from squadron.pipeline.git_ops import branch_work_count, parse_slice_index, read_integration_target
from squadron.pipeline.models import ActionResult, ValidationError
from squadron.pipeline.steps import StepTypeName
from squadron.pipeline.text_tail import tail_text

_logger = logging.getLogger(__name__)


class DispatchBranchWorkAction:
    """POST_ACTION event action: fail an implement dispatch that committed nothing."""

    name = "squadron.dispatch-branch-work"
    events = frozenset({EventType.POST_ACTION})

    def validate(self, config: dict[str, object]) -> list[ValidationError]:
        return []

    async def execute(self, context: EventContext) -> ActionResult:
        assert isinstance(context, PostActionContext)

        slice_param = context.params.get("slice")
        if (
            context.action_type != "dispatch"
            or context.step_type != StepTypeName.IMPLEMENT
            or not context.result.success
            or slice_param is None
            # A step that kept existing branch work dispatched nothing this run.
            or context.result.outputs.get(SKIPPED_KEY)
        ):
            return ActionResult(success=True, action_type=self.name, outputs={})

        # cf and git run as subprocesses; keep them off the event loop.
        branch, ahead, target = await asyncio.to_thread(self._count_work, context, slice_param)
        if ahead > 0:
            return ActionResult(success=True, action_type=self.name, outputs={})

        response = str(context.result.outputs.get("response", ""))
        msg = (
            f"implement dispatch completed but {branch} has no commits ahead of {target}; "
            f'the agent wrote no code. Agent\'s final text: "{tail_text(response)}"'
        )
        _logger.warning("dispatch post-condition: %s", msg)
        return ActionResult(success=False, action_type=self.name, outputs={}, error=msg)

    @staticmethod
    def _count_work(context: PostActionContext, slice_param: object) -> tuple[str, int, str]:
        target = read_integration_target(context.cf_client)
        branch, _ = slice_facts(parse_slice_index(slice_param), context.cf_client)
        return branch, branch_work_count(branch, target, cwd=context.cwd), target


register_event_action(DispatchBranchWorkAction())
