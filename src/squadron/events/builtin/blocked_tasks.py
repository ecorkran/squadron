"""squadron.blocked-tasks — POST_ACTION check that an implement dispatch left no
``BLOCKED:`` task markers (slice 947 D7).

An agent that cannot finish a task without the Project Manager writes a
``BLOCKED:`` line under it and stops. This pauses the run at that step, printing
the blocker text, so the review and close-out that follow never run on an
incomplete slice. It is bound before squadron.dispatch-branch-work: a blocked
agent often commits nothing, and the hand-off has to win over the "no commits"
failure.
"""

from __future__ import annotations

import asyncio
import logging

from squadron.events import EventType, register_event_action
from squadron.events.contexts import EventContext, PostActionContext
from squadron.integrations.context_forge import ContextForgeError, ContextForgeNotAvailable
from squadron.pipeline.actions.dispatch import SKIPPED_KEY
from squadron.pipeline.branch_ops import slice_task_paths
from squadron.pipeline.git_ops import parse_slice_index
from squadron.pipeline.models import ActionResult, ValidationError
from squadron.pipeline.steps import StepTypeName
from squadron.pr.tasks import BLOCKED_MARKER, parse_blocked_markers

_logger = logging.getLogger(__name__)

_MARKERS_NAMED = 3  # marker texts quoted in the pause message


class BlockedTasksAction:
    """POST_ACTION event action: pause an implement dispatch that left BLOCKED markers."""

    name = "squadron.blocked-tasks"
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

        try:
            # cf and file reads are blocking; keep them off the event loop.
            markers = await asyncio.to_thread(self._read_markers, context, slice_param)
        except (ContextForgeError, ContextForgeNotAvailable, ValueError) as exc:
            # cf could not say which task files the slice has (or the slice param is
            # not an index): the check cannot run, which is a failure, not a pass.
            msg = f"cannot check for {BLOCKED_MARKER} tasks: {exc}"
            _logger.error("blocked-tasks: %s", msg)
            return ActionResult(success=False, action_type=self.name, outputs={}, error=msg)
        except OSError as exc:
            msg = (
                f"cannot check for {BLOCKED_MARKER} tasks: cannot read task file {exc.filename}: {exc}"
            )
            _logger.error("blocked-tasks: %s", msg)
            return ActionResult(success=False, action_type=self.name, outputs={}, error=msg)

        if not markers:
            return ActionResult(success=True, action_type=self.name, outputs={})

        shown = "; ".join(markers[:_MARKERS_NAMED])
        msg = (
            f"{len(markers)} blocked task(s) need the Project Manager: {shown}. "
            f"Resolve them, remove the {BLOCKED_MARKER} lines, then resume: "
            f"sq run --resume {context.run_id}"
        )
        _logger.warning("blocked-tasks: %s", msg)
        return ActionResult(
            success=False, action_type=self.name, outputs={}, error=msg, awaits_human=True
        )

    @staticmethod
    def _read_markers(context: PostActionContext, slice_param: object) -> tuple[str, ...]:
        markers: list[str] = []
        for path in slice_task_paths(context.cf_client, parse_slice_index(slice_param), context.cwd):
            markers.extend(parse_blocked_markers(path.read_text(encoding="utf-8")))
        return tuple(markers)


register_event_action(BlockedTasksAction())
