"""Where HEAD stood before and after an action that can commit (slice 202).

A dispatch agent commits its own work, and the commit action commits the document, so
neither is known to a loop by name. Stamping each such result with the HEAD it started
from and the HEAD it left lets a loop prove which commits its own actions made: the
stamps of consecutive actions must chain, and a gap means someone else committed.
"""

from __future__ import annotations

import asyncio

from squadron.pipeline.actions import ActionType
from squadron.pipeline.actions.protocol import Action
from squadron.pipeline.models import ActionContext, ActionResult
from squadron.review.git_utils import run_git

HEAD_BEFORE_KEY = "head_before"
HEAD_AFTER_KEY = "head_after"

# The actions that can move HEAD: an agent commits during a dispatch, and the commit
# action commits the planned paths. A review or checkpoint never commits.
STAMPED_ACTION_TYPES = frozenset({ActionType.DISPATCH, ActionType.COMMIT})


def read_head(cwd: str) -> str | None:
    """The sha HEAD names, or ``None`` when git cannot say (not a repository, no commits)."""
    result = run_git(["rev-parse", "--verify", "HEAD"], cwd=cwd)
    if result is None or result.returncode != 0:
        return None
    return result.stdout.strip()


async def execute_stamped(action: Action, context: ActionContext, action_type: str) -> ActionResult:
    """Run ``action``; for a type that can commit, stamp the HEAD it started from and left.

    Both stamps are written together or not at all, so a result with one is never
    mistaken for a chain link. A repository git cannot read leaves the result unstamped.
    """
    if action_type not in STAMPED_ACTION_TYPES:
        return await action.execute(context)
    before = await asyncio.to_thread(read_head, context.cwd)
    result = await action.execute(context)
    after = await asyncio.to_thread(read_head, context.cwd)
    if before is not None and after is not None:
        result.metadata[HEAD_BEFORE_KEY] = before
        result.metadata[HEAD_AFTER_KEY] = after
    return result
