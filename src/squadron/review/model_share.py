"""One model's part of an artifact's stamped production cost (#267).

Stamped as ``usageByModel: {<model>: {rounds, costUsd, completionTokens}}`` beside the
artifact's totals. It grows with the number of distinct models, not with rounds.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TypeGuard, cast

from squadron.core.usage import UsageRecord, add_optional, add_optional_float
from squadron.review.run_cost import KEY_COMPLETION_TOKENS, KEY_COST_USD

_logger = logging.getLogger(__name__)

USAGE_BY_MODEL_KEY = "usageByModel"
#: A round whose provider reported no model is still counted, under a name no model has.
UNKNOWN_MODEL = "unknown"
_ROUNDS_KEY = "rounds"


@dataclass(frozen=True)
class ModelShare:
    """The rounds one model ran on an artifact and what they cost."""

    rounds: int
    cost_usd: float | None  # None when none of its rounds was priced; never $0
    completion_tokens: int | None

    def plus(self, record: UsageRecord) -> ModelShare:
        return ModelShare(
            rounds=self.rounds + 1,
            cost_usd=add_optional_float(self.cost_usd, record.cost_usd),
            completion_tokens=add_optional(self.completion_tokens, record.usage.completion),
        )

    def frontmatter_fields(self) -> dict[str, object]:
        """The share's keys; an unreported amount is left out, not written as zero."""
        fields: dict[str, object] = {_ROUNDS_KEY: self.rounds}
        if self.cost_usd is not None:
            fields[KEY_COST_USD] = self.cost_usd
        if self.completion_tokens is not None:
            fields[KEY_COMPLETION_TOKENS] = self.completion_tokens
        return fields


def read_model_shares(path: Path, front: Mapping[str, object]) -> dict[str, ModelShare]:
    """The stamped per-model split; empty when absent, or when malformed (one WARNING)."""
    raw = front.get(USAGE_BY_MODEL_KEY)
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        return _malformed(path, raw)
    entries = cast("Mapping[object, object]", raw)
    shares: dict[str, ModelShare] = {}
    for model, entry in entries.items():
        share = _share(entry)
        if share is None:
            return _malformed(path, entries)
        shares[str(model)] = share
    return shares


def _share(entry: object) -> ModelShare | None:
    if not isinstance(entry, Mapping):
        return None
    values = cast("Mapping[str, object]", entry)
    rounds = values.get(_ROUNDS_KEY)
    cost = values.get(KEY_COST_USD)
    completion = values.get(KEY_COMPLETION_TOKENS)
    if not _is_int(rounds) or rounds < 1:
        return None
    if cost is not None and (isinstance(cost, bool) or not isinstance(cost, int | float)):
        return None
    if completion is not None and not _is_int(completion):
        return None
    return ModelShare(
        rounds=rounds, cost_usd=None if cost is None else float(cost), completion_tokens=completion
    )


def _is_int(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool)


def _malformed(path: Path, value: object) -> dict[str, ModelShare]:
    _logger.warning(
        "usage stamp: %s has malformed %s: %.200r; the split restarts",
        path,
        USAGE_BY_MODEL_KEY,
        value,
    )
    return {}
