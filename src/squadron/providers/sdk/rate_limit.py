"""Shared rate-limit detection and backoff for SDK-backed paths.

Both the SDK agent and the pipeline's SDK session retry on provider
throttling. They previously carried independent copies of the retry budget,
the marker string, and (in one case) no backoff at all — which is how the
agent's skip path came to swallow the notice the retry path was waiting for.
One home for all three so the paths cannot drift apart again.
"""

from __future__ import annotations

from dataclasses import dataclass

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

#: Substring identifying a rate-limit notice, wherever it surfaces. The CLI
#: emits it as a ``rate_limit_event`` message; on an SDK version without a
#: case for that type it arrives as a ``MessageParseError`` naming it. One
#: constant so the skip path and the retry path cannot disagree about what
#: counts as throttling — they previously did, and the skip silently
#: disabled the backoff.
RATE_LIMIT_MARKER = "rate_limit"


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
