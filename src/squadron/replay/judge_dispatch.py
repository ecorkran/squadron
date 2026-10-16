"""The production judge dispatcher: a text-only one-shot call to the judge's model (D5)."""

from __future__ import annotations

import time

from squadron.pipeline.actions.dispatch import one_shot_dispatch_with_telemetry
from squadron.pipeline.resolver import ModelResolver
from squadron.pipeline.usage_capture import UsageCapture
from squadron.replay.judging import JudgeCallError, JudgeDispatcher, JudgeReply

_STEP_NAME = "replay-judge"


def one_shot_judge_dispatcher(alias: str) -> JudgeDispatcher:
    """A dispatcher for ``alias``, resolved once so a bad alias fails before any call.

    Tools are off (``allowed_tools=[]``): the judge compares what it is given, and an agent
    with file tools could read the original artifact out of the repository.
    """
    resolved = ModelResolver().resolve_full(alias)
    if resolved.profile is None:
        raise JudgeCallError(f"alias '{alias}' has no profile, so it cannot be dispatched")
    profile = resolved.profile
    capture = UsageCapture(set())

    async def dispatch(prompt: str) -> JudgeReply:
        usage_metadata: dict[str, object] = {}
        started = time.monotonic()
        try:
            text, _ = await one_shot_dispatch_with_telemetry(
                prompt=prompt,
                model_id=resolved.model_id,
                profile_name=profile,
                step_name=_STEP_NAME,
                allowed_tools=[],
                usage_metadata=usage_metadata,
            )
        except Exception as exc:
            # The model-call boundary: provider failure modes (network, auth, API errors)
            # are not enumerable here. Re-raised as the one error the judge core handles.
            raise JudgeCallError(f"{type(exc).__name__}: {exc}") from exc
        record = capture.record_from_message(
            resolved, usage_metadata, started=started, model=resolved.model_id, effort_sent=None
        )
        return JudgeReply(text=text, usage=record)

    return dispatch
