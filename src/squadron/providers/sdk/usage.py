"""Reading usage, turns, and cost off a Claude SDK ``ResultMessage`` (slice 175 D1, D2).

The only code that knows the SDK's usage key names. The ``usage`` dict is passed through
from the CLI untyped, so every value is read defensively: a malformed one becomes ``None``
with a WARNING and its siblings are kept. Per-message usage and ``model_usage`` are never
read (D2): only the result's top-level ``usage`` is authoritative.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from claude_agent_sdk import ResultMessage

from squadron.core.usage import TokenUsage, add_optional
from squadron.logging import get_logger

_log = get_logger("squadron.providers.sdk.usage")

_INPUT = "input_tokens"
_CACHE_READ = "cache_read_input_tokens"
_CACHE_WRITE = "cache_creation_input_tokens"
_OUTPUT = "output_tokens"


def read_result_usage(msg: ResultMessage) -> tuple[TokenUsage | None, int | None, float | None]:
    """Return ``(tokens, turns, total_cost_usd)`` from one result; each ``None`` when unreported.

    The cost is the session's running total, not this result's spend: pass it through
    the connection's ``SessionCostMeter``.

    D1 mapping: ``prompt`` counts every input token, so it is ``input_tokens`` plus both
    cache classes; ``prompt`` is ``None`` only when ``input_tokens`` is missing. The SDK
    reports no reasoning split, so ``reasoning`` stays ``None``.
    """
    turns = _strict_int(msg.num_turns)
    raw_cost: object = msg.total_cost_usd
    cost = (
        float(raw_cost)
        if isinstance(raw_cost, int | float) and not isinstance(raw_cost, bool)
        else None
    )
    if msg.usage is None:
        return None, turns, cost
    usage: dict[str, Any] = msg.usage
    uncached = _usage_int(usage, _INPUT)
    cached = _usage_int(usage, _CACHE_READ)
    cache_write = _usage_int(usage, _CACHE_WRITE)
    prompt = None
    if uncached is not None:
        prompt = add_optional(add_optional(uncached, cached), cache_write)
    tokens = TokenUsage(
        prompt=prompt,
        cached=cached,
        cache_write=cache_write,
        completion=_usage_int(usage, _OUTPUT),
    )
    return tokens, turns, cost


@dataclass
class SessionCostMeter:
    """Turns ``total_cost_usd``, a running total for the CLI session, into per-result cost.

    One meter per SDK connection; replace it whenever the connection is replaced. A
    total below the last one means the CLI zeroed its totals (conversation reset), so
    the new total is charged in full.
    """

    last_total: float = 0.0

    def charge(self, total: float | None) -> float | None:
        """Cost spent since the previous result on this connection; ``None`` when unreported."""
        if total is None:
            return None
        if total < self.last_total:
            self.last_total = 0.0
        spent = total - self.last_total
        self.last_total = total
        return spent


def _usage_int(usage: dict[str, Any], key: str) -> int | None:
    """One count from the usage dict; a missing key is ``None``, a malformed one warns."""
    if key not in usage:
        return None
    value = usage[key]
    count = _strict_int(value)
    if count is None:
        _log.warning("SDK result usage field %s is not an int: %.200r", key, value)
    return count


def _strict_int(value: object) -> int | None:
    """``value`` when it is an int (bool is not), else ``None``."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value
