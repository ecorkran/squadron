"""Shared rate-limit detection and backoff for SDK-backed paths.

Both the SDK agent and the pipeline's SDK session retry on provider
throttling, reading their signal from the SDK's typed ``RateLimitEvent``
(``rate_limit_info.status``). They previously carried independent copies of
the retry budget, the marker string, and (in one case) no backoff at all —
which is how the agent's skip path came to swallow the notice the retry path
was waiting for. One home for all three so the paths cannot drift apart
again.

Before the SDK's parser understood ``rate_limit_event`` natively (< 0.2.152),
this module also carried a monkey-patch that taught the pinned parser to
accept the type. The floor was raised past that version and the patch was
removed — see squadron issue #30.
"""

from __future__ import annotations

from dataclasses import dataclass

from claude_agent_sdk import ClaudeSDKError, RateLimitEvent

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
#: (e.g. a genuine 429 surfaced as ``ClaudeSDKError``). A typed
#: ``RateLimitEvent`` is classified structurally instead — never by this
#: string; see ``event_blocks``.
RATE_LIMIT_MARKER = "rate_limit"

_STATUS_REJECTED = "rejected"


def event_blocks(event: RateLimitEvent) -> bool:
    """True when a typed SDK rate-limit event says requests are rejected."""
    return event.rate_limit_info.status == _STATUS_REJECTED


class RateLimitRejected(ClaudeSDKError):
    """A typed rate-limit event reporting ``rejected`` — a genuine throttle.

    Raised at the dispatch site when a parsed ``RateLimitEvent``'s status is
    ``rejected``, so the existing ``except ClaudeSDKError`` backoff loops
    catch it without restructuring.
    """


def is_throttle(exc: Exception) -> bool:
    """True for a typed throttle, or a genuine 429 surfaced as plain text."""
    if isinstance(exc, RateLimitRejected):
        return True
    return isinstance(exc, ClaudeSDKError) and RATE_LIMIT_MARKER in str(exc)


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
