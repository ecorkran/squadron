"""Cumulative production cost of one artifact, kept in its own frontmatter (slice 178 D2).

An artifact written by a pipeline carries the review cost keys (931 D10) summed over every
dispatch that wrote it, plus ``usageRounds`` and ``pricedRounds`` so a reader can say how
much of the total is priced. The file is the only store: each stamp reads the prior total,
adds one ``UsageRecord`` and writes the result back.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TypeGuard

from squadron.core.usage import UsageRecord, add_optional, add_optional_float
from squadron.review.frontmatter_usage import record_from_frontmatter
from squadron.review.run_cost import (
    KEY_CACHE_WRITE_TOKENS,
    KEY_CACHED_TOKENS,
    KEY_COMPLETION_TOKENS,
    KEY_COST_BASIS,
    KEY_COST_USD,
    KEY_DURATION_SECONDS,
    KEY_PROMPT_TOKENS,
    KEY_REASONING_TOKENS,
    KEY_TURNS,
    RunCost,
)

_logger = logging.getLogger(__name__)

USAGE_ROUNDS_KEY = "usageRounds"
PRICED_ROUNDS_KEY = "pricedRounds"

_COUNT_KEYS = (
    KEY_TURNS,
    KEY_PROMPT_TOKENS,
    KEY_CACHED_TOKENS,
    KEY_CACHE_WRITE_TOKENS,
    KEY_COMPLETION_TOKENS,
    KEY_REASONING_TOKENS,
)
_AMOUNT_KEYS = (KEY_DURATION_SECONDS, KEY_COST_USD)


@dataclass(frozen=True)
class ArtifactUsage:
    """What an artifact cost to produce so far, over ``rounds`` dispatches.

    ``cost.cost_usd`` sums only the ``priced_rounds`` that had a cost; an unpriced round is
    never counted as $0.
    """

    cost: RunCost
    rounds: int
    priced_rounds: int


def fold(prior: ArtifactUsage | None, record: UsageRecord) -> ArtifactUsage:
    """Add one dispatch's ``record`` to ``prior`` (175 D9: ``None`` survives until reported)."""
    base = prior or ArtifactUsage(cost=RunCost(), rounds=0, priced_rounds=0)
    total = base.cost
    cost = RunCost(
        turns=add_optional(total.turns, record.turns),
        usage=total.usage.plus(record.usage),
        duration_seconds=add_optional_float(total.duration_seconds, record.duration_seconds),
        cost_usd=add_optional_float(total.cost_usd, record.cost_usd),
    )
    return ArtifactUsage(
        cost=cost,
        rounds=base.rounds + 1,
        priced_rounds=base.priced_rounds + (0 if record.cost_usd is None else 1),
    )


def artifact_usage_fields(usage: ArtifactUsage) -> dict[str, object]:
    """The frontmatter keys to stamp. ``costBasis`` is left out: totals mix bases (#231)."""
    fields = {k: v for k, v in usage.cost.frontmatter_fields().items() if k != KEY_COST_BASIS}
    fields[USAGE_ROUNDS_KEY] = usage.rounds
    fields[PRICED_ROUNDS_KEY] = usage.priced_rounds
    return fields


def read_artifact_usage(path: Path, front: Mapping[str, object]) -> ArtifactUsage | None:
    """The total stamped in ``front``, or ``None`` when absent or malformed.

    A malformed total logs one WARNING naming ``path`` and the key, so the caller restarts
    from the next record rather than building on a number it cannot trust.
    """
    if USAGE_ROUNDS_KEY not in front:
        return None
    rounds = front[USAGE_ROUNDS_KEY]
    priced = front.get(PRICED_ROUNDS_KEY)
    if not _is_int(rounds) or rounds < 1:
        return _malformed(path, USAGE_ROUNDS_KEY, rounds)
    if not _is_int(priced) or priced < 0:
        return _malformed(path, PRICED_ROUNDS_KEY, priced)
    for key in _COUNT_KEYS:
        if front.get(key) is not None and not _is_int(front[key]):
            return _malformed(path, key, front[key])
    for key in _AMOUNT_KEYS:
        value = front.get(key)
        if value is not None and (isinstance(value, bool) or not isinstance(value, int | float)):
            return _malformed(path, key, value)
    cost = RunCost.from_record(record_from_frontmatter(path, front))
    return ArtifactUsage(cost=cost, rounds=rounds, priced_rounds=priced)


def _is_int(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool)


def _malformed(path: Path, key: str, value: object) -> None:
    _logger.warning("usage stamp: %s has malformed %s: %.200r; total restarts", path, key, value)
