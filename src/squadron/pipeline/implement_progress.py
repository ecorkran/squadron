"""Holding an implement dispatch to its task file (issue #293).

An SDK implementer can end its turn with task items still unchecked, most often to
wait for a background task-checker whose notification a one-shot dispatch never
delivers. This reads the slice's task files after the dispatch and re-prompts the same
session until every item is checked, a ``BLOCKED:`` line hands off to the Project
Manager, or the session stops making progress.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from squadron.pipeline.branch_ops import slice_task_paths
from squadron.pipeline.commit_plan import SLICE_PARAM
from squadron.pipeline.git_ops import parse_slice_index
from squadron.pipeline.sdk_turns import SessionReply
from squadron.pipeline.steps import StepTypeName
from squadron.pipeline.steps.phase import RULES_STEP_PARAM
from squadron.pr.tasks import BLOCKED_MARKER, parse_blocked_markers, parse_task_items
from squadron.providers.errors import ProviderError

if TYPE_CHECKING:
    from squadron.pipeline.sdk_session import SDKExecutionSession
    from squadron.review.persistence import CfClientProtocol

_logger = logging.getLogger(__name__)

#: Consecutive continuations that leave no fewer unchecked items before the step gives up.
MAX_STALLED_CONTINUATIONS = 2

_ITEMS_NAMED = 3  # unchecked items quoted in a prompt or failure message


@dataclass(frozen=True)
class TaskProgress:
    """The unchecked items and ``BLOCKED`` markers across a slice's task files."""

    unchecked: tuple[str, ...]
    blocked: tuple[str, ...]

    @property
    def needs_continuation(self) -> bool:
        """Items remain and nothing has been handed to the Project Manager."""
        return bool(self.unchecked) and not self.blocked

    def preview(self) -> str:
        """The first few unchecked items, for a prompt or message."""
        return "; ".join(self.unchecked[:_ITEMS_NAMED])


def implement_slice_index(params: Mapping[str, object]) -> int | None:
    """The slice an implement dispatch works on; ``None`` for any other dispatch."""
    if params.get(RULES_STEP_PARAM) != StepTypeName.IMPLEMENT or params.get(SLICE_PARAM) is None:
        return None
    return parse_slice_index(params[SLICE_PARAM])


def read_task_progress(cf_client: CfClientProtocol, slice_index: int, cwd: str) -> TaskProgress:
    """Read the slice's task files; a cf error or unreadable file propagates."""
    unchecked: list[str] = []
    blocked: list[str] = []
    for path in slice_task_paths(cf_client, slice_index, cwd):
        text = path.read_text(encoding="utf-8")
        unchecked.extend(parse_task_items(text).unchecked)
        blocked.extend(parse_blocked_markers(text))
    return TaskProgress(unchecked=tuple(unchecked), blocked=tuple(blocked))


def continuation_prompt(progress: TaskProgress) -> str:
    """The follow-up that sends a stopped implementer back to its unchecked items."""
    return (
        f"The task file(s) for this slice still have {len(progress.unchecked)} unchecked "
        f"item(s); first: {progress.preview()}. You have not finished. For each unchecked "
        "item: if its work is done, check it off; otherwise do the work, then check it off. "
        "Run the task-checker agent in the foreground, never in the background, or edit "
        "the checkboxes directly: this session never delivers a background agent's "
        "notification, so do not end your turn to wait for one. Keep going until every "
        "item is checked. If you cannot continue without the Project Manager, write a "
        f"line starting with `{BLOCKED_MARKER}:` and the reason under the task and stop. "
        "Do not end your turn for any other reason."
    )


def unfinished_message(progress: TaskProgress) -> str:
    """The failure text for an implement step that stopped with items still unchecked."""
    return (
        f"implement dispatch ended with {len(progress.unchecked)} unchecked task item(s) "
        f"after {MAX_STALLED_CONTINUATIONS} continuations that checked off none; "
        f"first: {progress.preview()}. Rerun the step to continue."
    )


async def continue_until_finished(
    session: SDKExecutionSession,
    reply: SessionReply,
    read_progress: Callable[[], TaskProgress],
) -> tuple[SessionReply, TaskProgress]:
    """Re-prompt ``session`` while task items remain, returning the combined reply.

    ``read_progress`` is blocking (cf and file reads) and runs off the event loop. The
    loop ends when nothing needs continuing, or after ``MAX_STALLED_CONTINUATIONS`` in a
    row that leave no fewer unchecked items; each round that checks something off resets
    the count. A provider error carries the spend of every round so far.
    """
    progress = await asyncio.to_thread(read_progress)
    stalled = 0
    while progress.needs_continuation and stalled < MAX_STALLED_CONTINUATIONS:
        before = len(progress.unchecked)
        _logger.warning(
            "implement: %d unchecked task item(s) after the dispatch ended; continuing "
            "the session (first: %s)",
            before,
            progress.preview(),
        )
        try:
            more = await session.dispatch(continuation_prompt(progress))
        except ProviderError as exc:
            if exc.telemetry is not None:
                exc.telemetry = reply.telemetry.plus(exc.telemetry)
            else:
                exc.telemetry = reply.telemetry
            raise
        reply = SessionReply(
            text=f"{reply.text}\n\n{more.text}", telemetry=reply.telemetry.plus(more.telemetry)
        )
        progress = await asyncio.to_thread(read_progress)
        stalled = stalled + 1 if len(progress.unchecked) >= before else 0
    return reply, progress
