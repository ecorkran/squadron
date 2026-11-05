"""The production judge dispatcher: a text-only one-shot call to the judge's model (D5)."""

from __future__ import annotations

import time

from squadron.core.models import Effort
from squadron.pipeline.actions.dispatch import one_shot_dispatch_with_telemetry
from squadron.pipeline.resolver import ModelResolver, ResolvedModel
from squadron.pipeline.usage_capture import UsageCapture, effort_sent_by_profile, read_effort_sent
from squadron.replay.judging import JudgeCallError, JudgeDispatcher, JudgeReply

_STEP_NAME = "replay-judge"


def _resolve_judge(alias: str) -> tuple[ResolvedModel, str]:
    """The judge's resolved alias and its profile; a profile-less alias cannot be called."""
    resolved = ModelResolver().resolve_full(alias)
    if resolved.profile is None:
        raise JudgeCallError(f"alias '{alias}' has no profile, so it cannot be dispatched")
    return resolved, resolved.profile


def judge_effort_sent(alias: str) -> Effort | None:
    """The effort a call to judge ``alias`` sends, known before any call is made.

    The alias's effort only counts where the profile's provider applies it, the same
    rule the dispatcher records its calls by (slice 420 D3).
    """
    resolved, profile = _resolve_judge(alias)
    return effort_sent_by_profile(profile, resolved.effort)


def one_shot_judge_dispatcher(alias: str) -> JudgeDispatcher:
    """A dispatcher for ``alias``, resolved once so a bad alias fails before any call.

    Tools are off (``allowed_tools=[]``): the judge compares what it is given, and an agent
    with file tools could read the original artifact out of the repository. The alias's
    effort is sent and recorded on each reply's usage.
    """
    resolved, profile = _resolve_judge(alias)
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
                effort=resolved.effort,
                usage_metadata=usage_metadata,
            )
        except Exception as exc:
            # The model-call boundary: provider failure modes (network, auth, API errors)
            # are not enumerable here. Re-raised as the one error the judge core handles.
            raise JudgeCallError(f"{type(exc).__name__}: {exc}") from exc
        record = capture.record_from_message(
            resolved,
            usage_metadata,
            started=started,
            model=resolved.model_id,
            effort_sent=read_effort_sent(usage_metadata),
        )
        return JudgeReply(text=text, usage=record)

    return dispatch
