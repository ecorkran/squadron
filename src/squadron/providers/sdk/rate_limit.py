"""Shared rate-limit detection and backoff for SDK-backed paths.

Both the SDK agent and the pipeline's SDK session retry on provider
throttling. They previously carried independent copies of the retry budget,
the marker string, and (in one case) no backoff at all — which is how the
agent's skip path came to swallow the notice the retry path was waiting for.
One home for all three so the paths cannot drift apart again.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

#: Default retry budget. Callers that know their workload is heavier (the
#: metrology audit, whose subagent fan-out multiplies request rate) override
#: it per agent.
MAX_RATE_LIMIT_RETRIES = 10

#: Exponential backoff between rate-limit retries, in seconds: 2, 4, 8, ...
#: capped at ``RATE_LIMIT_MAX_BACKOFF_S``.
#:
#: The delay previously did not exist. The retry loops carried a comment
#: saying "the CLI handles the backoff delay" and slept for nothing —
#: measured at 11 attempts in 0.1ms, which hammers the rate limiter rather
#: than waiting for it and can *cause* the limit it is trying to survive.
RATE_LIMIT_BASE_BACKOFF_S = 2.0
RATE_LIMIT_MAX_BACKOFF_S = 60.0

#: Substring identifying a rate-limit notice in a plain SDK error's text
#: (e.g. a genuine 429 surfaced as ``ClaudeSDKError``). Parse failures carry
#: a payload and are classified structurally below — never by this string.
RATE_LIMIT_MARKER = "rate_limit"

#: The CLI message type behind most "rate limit" sightings. Its own schema
#: description reads "Rate limit event emitted when rate limit info
#: changes" — it is a *status* event feeding the usage indicator, fired on
#: any change, and the CLI's own SDK adapter ignores it
#: (``[sdkMessageAdapter] Ignoring rate_limit_event message``). Payload:
#: ``{type, rate_limit_info: {status: allowed|allowed_warning|rejected,
#: resetsAt?, rateLimitType?, utilization?, ...}, uuid, session_id}``.
#: Only ``rejected`` means requests are actually being blocked. Treating
#: every event as a throttle made squadron pause and restart the stream on
#: each usage-info change — an interactive session receives the identical
#: events and shows nothing.
RATE_LIMIT_EVENT_TYPE = "rate_limit_event"

_STATUS_REJECTED = "rejected"


def is_rate_limit_event(data: dict[str, object] | None) -> bool:
    """True when a parse-failure payload is the CLI's rate-limit status event."""
    return bool(data) and data.get("type") == RATE_LIMIT_EVENT_TYPE


def rate_limit_event_blocks(data: dict[str, object] | None) -> bool:
    """True when the event says requests are being rejected — a real throttle.

    ``allowed`` and ``allowed_warning`` are usage-meter updates; only
    ``rejected`` warrants backing off. A malformed payload is treated as
    informational: the failure mode of guessing "throttled" is pausing and
    restarting a healthy stream on every usage change, which is the exact
    defect this classification exists to remove.
    """
    if not data:
        return False
    info = data.get("rate_limit_info")
    if not isinstance(info, dict):
        return False
    status: object = cast("dict[str, object]", info).get("status")
    return status == _STATUS_REJECTED


def rate_limit_backoff_s(attempt: int, cap_s: float = RATE_LIMIT_MAX_BACKOFF_S) -> float:
    """Seconds to wait before rate-limit retry ``attempt`` (1-based)."""
    return min(RATE_LIMIT_BASE_BACKOFF_S * (2 ** (attempt - 1)), cap_s)


@dataclass
class RateLimitStats:
    """How much throttling a run absorbed.

    Per-event warnings say throttling happened; they do not say what it
    cost. Without a total, comparing one run to another — or squadron to a
    manual run of the same skill — stays anecdotal.

    Mutable and cumulative: one instance per agent, updated as retries fire.
    """

    throttles: int = 0
    waited_s: float = 0.0

    def record(self, delay_s: float) -> None:
        self.throttles += 1
        self.waited_s += delay_s

    def summary(self) -> str:
        """One line for an operator, or empty when nothing was throttled."""
        if self.throttles == 0:
            return ""
        return f"{self.throttles} rate-limit pauses, {self.waited_s:.0f}s spent waiting"
