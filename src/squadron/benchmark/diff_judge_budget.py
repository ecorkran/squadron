"""The run cap on judge spend (slice 426 D16).

The cap is checked before each judge call. A call that crosses it is the last: the run
stops, every record already written stays, and the overshoot is at most one call. A reply
that reports no cost counts at the per-call figure, and so does a call that fails or times
out (it may have been billed), so no call is ever counted as free.
"""

from __future__ import annotations

import asyncio

from squadron.replay.judging import JudgeCallError, JudgeDispatcher, JudgeReply


class JudgeCapReached(Exception):
    """The run cap is spent; judging stops with every earlier record kept."""

    def __init__(self, spent_usd: float, cap_usd: float) -> None:
        super().__init__(f"run cap reached: spent ${spent_usd:.2f} of ${cap_usd:.2f}")
        self.spent_usd = spent_usd
        self.cap_usd = cap_usd


class JudgeBudget:
    """What one judge invocation has spent against its run cap."""

    def __init__(self, cap_usd: float, per_call_usd: float) -> None:
        self.cap_usd = cap_usd
        self.per_call_usd = per_call_usd
        self.spent_usd = 0.0
        self.unpriced_calls = 0

    def check(self) -> None:
        """Raise ``JudgeCapReached`` when nothing is left to spend; the next call is refused."""
        if self.spent_usd >= self.cap_usd:
            raise JudgeCapReached(self.spent_usd, self.cap_usd)

    def charge(self, reply: JudgeReply) -> None:
        """Count a finished call: its reported cost, else the per-call figure."""
        usage = reply.usage
        if usage is None or usage.cost_usd is None:
            self.charge_unpriced()
        else:
            self.spent_usd += usage.cost_usd

    def charge_unpriced(self) -> None:
        """Count a call with no reported cost (no reply, or a reply without usage) at the figure."""
        self.unpriced_calls += 1
        self.spent_usd += self.per_call_usd


def metered(dispatcher: JudgeDispatcher, budget: JudgeBudget) -> JudgeDispatcher:
    """A dispatcher that charges *budget* for every call, returned, failed or timed out.

    Charging happens per call, not per pair, so the first call of a pair the cap then stops
    is still counted. The caller still sees the failure; a timeout reaches this wrapper as a
    cancellation, which is charged and re-raised.
    """

    async def dispatch(prompt: str) -> JudgeReply:
        try:
            reply = await dispatcher(prompt)
        except (JudgeCallError, asyncio.CancelledError):
            budget.charge_unpriced()
            raise
        budget.charge(reply)
        return reply

    return dispatch
