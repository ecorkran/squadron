"""Squash action — collapse the newest planning commit run (slice 948 D6).

A thin wrapper over ``pipeline/squash.py``, which ``sq squash`` calls too, so SDK and
prompt-only runs find and rewrite the same run.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from squadron.pipeline.actions import ActionType, register_action
from squadron.pipeline.commit_plan import CommitTargetError
from squadron.pipeline.git_ops import SliceNotInPlanError, parse_slice_index, read_integration_target
from squadron.pipeline.models import ActionContext, ActionResult, ValidationError
from squadron.pipeline.squash import (
    NothingToSquash,
    SquashKind,
    SquashRefusedError,
    SquashRewriteError,
    SquashTarget,
    apply_squash,
    plan_squash,
)
from squadron.pipeline.steps.squash import INDEX_PARAM, KIND_PARAM

SQUASHED_OUTPUT = "squashed"
COMMIT_OUTPUT = "commit"
BACKUP_TAG_OUTPUT = "backup_tag"


class SquashAction:
    """Pipeline action that collapses a planning loop's commits into one."""

    @property
    def action_type(self) -> str:
        return ActionType.SQUASH

    def validate(self, config: dict[str, object]) -> list[ValidationError]:
        """The step type validates kind and index; nothing more is checkable before run time."""
        return []

    async def execute(self, context: ActionContext) -> ActionResult:
        try:
            target = SquashTarget(
                SquashKind(str(context.params.get(KIND_PARAM))),
                parse_slice_index(context.params.get(INDEX_PARAM)),
            )
        except ValueError as exc:
            return self._failure(str(exc))
        try:
            # git and cf run as subprocesses; keep them off the event loop.
            outputs = await asyncio.to_thread(_squash, target, context)
        except (
            SquashRefusedError,
            SquashRewriteError,
            CommitTargetError,
            SliceNotInPlanError,
            FileNotFoundError,
        ) as exc:
            # This step failed; the next item may still succeed. Environment faults raise
            # past here and end the run, as they do for branch and commit: git that
            # cannot answer (GitEnvironmentError, which also wraps a cf failure to read
            # the target) and cf failing outright (ContextForgeError).
            return self._failure(str(exc))
        return ActionResult(success=True, action_type=self.action_type, outputs=outputs)

    def _failure(self, error: str) -> ActionResult:
        return ActionResult(success=False, action_type=self.action_type, outputs={}, error=error)


def _squash(target: SquashTarget, context: ActionContext) -> dict[str, object]:
    cwd = Path(context.cwd)
    branch = read_integration_target(context.cf_client)
    plan = plan_squash(target, branch, cwd, context.cf_client)
    if isinstance(plan, NothingToSquash):
        return {SQUASHED_OUTPUT: 0}
    return {
        SQUASHED_OUTPUT: len(plan.commits),
        COMMIT_OUTPUT: apply_squash(plan, cwd),
        BACKUP_TAG_OUTPUT: plan.backup_tag,
    }


register_action(ActionType.SQUASH, SquashAction())
