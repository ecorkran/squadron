"""squadron.frontmatter-gate — COMMIT action wrapping ``cf validate frontmatter``.

Refactors slice 172's bespoke installer-driven gate onto the events
mechanism (design D8). Exit mapping preserves 172's D6 posture: a gate that
cannot determine validity must not pass. Uses
``asyncio.create_subprocess_exec`` — never a blocking subprocess call inside
an async function (project async rule).
"""

from __future__ import annotations

import asyncio
import logging

from squadron.events import EventType, register_event_action
from squadron.events.contexts import CommitContext, EventContext
from squadron.pipeline.models import ActionResult, ValidationError

_logger = logging.getLogger(__name__)

_MISSING_CF_MESSAGE = (
    "'cf' is not on PATH — cannot run cf validate frontmatter. "
    "Install context-forge, or disable this action in events.yaml."
)
_COULD_NOT_RUN_MESSAGE = (
    "cf could not run the validation — if this repo is not a registered cf "
    "project, run 'cf init' once, or disable this action in events.yaml."
)


class FrontmatterGateAction:
    """COMMIT event action: reject a commit whose staged markdown fails
    ``cf validate frontmatter``."""

    name = "squadron.frontmatter-gate"
    events = frozenset({EventType.COMMIT})

    def validate(self, config: dict[str, object]) -> list[ValidationError]:
        return []

    async def execute(self, context: EventContext) -> ActionResult:
        assert isinstance(context, CommitContext)

        args = ["cf", "validate", "frontmatter", *context.staged_paths]
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                cwd=context.cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_bytes, stderr_bytes = await proc.communicate()
        except FileNotFoundError:
            _logger.warning("frontmatter-gate: %s", _MISSING_CF_MESSAGE)
            return ActionResult(
                success=False, action_type=self.name, outputs={}, error=_MISSING_CF_MESSAGE
            )

        stdout = stdout_bytes.decode(errors="replace")
        stderr = stderr_bytes.decode(errors="replace")
        exit_code = proc.returncode

        if exit_code == 0:
            return ActionResult(success=True, action_type=self.name, outputs={"stdout": stdout})

        if exit_code == 2:
            message = f"{_COULD_NOT_RUN_MESSAGE}\n{stdout}{stderr}".strip()
            _logger.warning("frontmatter-gate: %s", message)
            return ActionResult(success=False, action_type=self.name, outputs={}, error=message)

        message = stdout.strip() or stderr.strip() or f"cf validate frontmatter exited {exit_code}"
        _logger.warning("frontmatter-gate: %s", message)
        return ActionResult(success=False, action_type=self.name, outputs={}, error=message)


register_event_action(FrontmatterGateAction())
