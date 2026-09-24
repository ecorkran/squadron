"""Collecting a review agent's reply and telemetry across one or more turns.

The recovery prompt below is sent when the first turn ended without a review. It names no
verdict or finding: the model's own instructions already define the format, and any
example here is what a model with nothing left to say would copy.

A review normally takes one ``handle_message`` call. The recovery turn (#92) sends a second
on the same agent, so the prose and telemetry both have to accumulate rather than be
overwritten: prose parts append, per-call counts sum, and the stop reason is the latest.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from squadron.core.models import (
    RATE_LIMIT_EVENT_TYPE,
    SDK_RESULT_TYPE,
    TOOL_RESULT_TYPE,
    TOOL_USE_TYPE,
    Message,
    MessageType,
)
from squadron.review.models import ReviewResult, Verdict

#: SDK message kinds that narrate the run rather than carry review prose. SDK providers emit
#: both an AssistantMessage and a ResultMessage with identical content (the result is the
#: duplicate), plus tool_use/tool_result narration and informational rate-limit notices
#: (issue #23 class). Non-SDK providers never set sdk_type and are unaffected.
_NON_PROSE_SDK_TYPES = (SDK_RESULT_TYPE, TOOL_USE_TYPE, TOOL_RESULT_TYPE, RATE_LIMIT_EVENT_TYPE)

FINISH_REVIEW_PROMPT = (
    "Your previous reply ended before the review was written. If you still need to read "
    "something, use your tools now. This reply must end with the complete review in the "
    "output structure your instructions require, stating the verdict and every finding."
)


@dataclass
class TurnCapture:
    """Everything a review reads back from its agent, accumulated across turns.

    ``None`` means "not reported" and survives to ``ReviewResult`` as such — never
    fabricated into a plausible-looking value (slice 918).
    """

    text_parts: list[str] = field(default_factory=list[str])
    tools_given: list[str] | None = None
    tool_calls_made: int | None = None
    suppressed_reason: str | None = None
    stop_reason: str | None = None
    reasoning_chars: int | None = None
    failed_tool_calls: int | None = None

    @property
    def raw_output(self) -> str:
        return "\n".join(self.text_parts)


def ended_mid_task(result: ReviewResult) -> bool:
    """Did the model say something, yet emit no review the parser could read? (#92)

    Every captured case ended with a clean stop partway through the work: a narrated next
    step, or the model's own tool-call markup written as text. An empty response is not
    this — the provider already fails that turn (#84).
    """
    return result.verdict is Verdict.UNKNOWN and not result.findings and bool(result.raw_output.strip())


def _add(total: int | None, value: int | None) -> int | None:
    """Sum two per-turn counts, keeping ``None`` only when neither turn reported."""
    if value is None:
        return total
    return (total or 0) + value


async def collect_turn(agent: Any, *, content: str, recipient: str, capture: TurnCapture) -> None:
    """Send ``content`` to ``agent`` and fold its reply into ``capture``.

    Telemetry rides the final Message's metadata (design D4), and is read from every
    response rather than only the prose ones, because the filtered-out SDK result message
    can be the last one yielded. Within one call the last stamped value wins; across calls
    counts sum, since each provider stamps per-``handle_message`` counts.
    """
    message = Message(
        sender="review-system",
        recipients=[recipient],
        content=content,
        message_type=MessageType.chat,
    )
    turn_calls: int | None = None
    turn_failures: int | None = None
    turn_reasoning: int | None = None
    async for response in agent.handle_message(message):
        metadata: dict[str, Any] = response.metadata
        given = metadata.get("tools_given")
        if given is not None:
            capture.tools_given = given
            turn_calls = metadata.get("tool_calls_made", 0)
        # Guarded per key rather than on one of them: a later response that stamps nothing
        # must not erase what an earlier one reported. Counts are checked against None, not
        # truthiness — a stamped 0 is a real answer.
        if metadata.get("tools_suppressed_reason") is not None:
            capture.suppressed_reason = metadata["tools_suppressed_reason"]
        if metadata.get("stop_reason") is not None:
            capture.stop_reason = metadata["stop_reason"]
        if metadata.get("reasoning_chars") is not None:
            turn_reasoning = metadata["reasoning_chars"]
        if metadata.get("failed_tool_calls") is not None:
            turn_failures = metadata["failed_tool_calls"]
        if metadata.get("sdk_type") in _NON_PROSE_SDK_TYPES:
            continue
        capture.text_parts.append(response.content)

    capture.tool_calls_made = _add(capture.tool_calls_made, turn_calls)
    capture.failed_tool_calls = _add(capture.failed_tool_calls, turn_failures)
    capture.reasoning_chars = _add(capture.reasoning_chars, turn_reasoning)
