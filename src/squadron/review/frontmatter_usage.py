"""Read the 931/175 cost keys out of an artifact's frontmatter as a ``UsageRecord``.

Shared by ``sq stats reviews`` and the artifact usage stamp (slice 178), so the key
names and the "bad field becomes None, with a WARNING" rule live in one place.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from pathlib import Path

from squadron.core.usage import CostBasis, TokenUsage, UsageRecord
from squadron.models.aliases import get_all_aliases
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
)

_logger = logging.getLogger(__name__)

_INT_KEYS = {
    "prompt": KEY_PROMPT_TOKENS,
    "cached": KEY_CACHED_TOKENS,
    "cache_write": KEY_CACHE_WRITE_TOKENS,
    "completion": KEY_COMPLETION_TOKENS,
    "reasoning": KEY_REASONING_TOKENS,
}


def record_from_frontmatter(path: Path, front: Mapping[str, object]) -> UsageRecord:
    """Map the 931/175 frontmatter cost keys onto a ``UsageRecord``; bad fields become None."""
    tokens = TokenUsage(**{name: _int(path, front, key) for name, key in _INT_KEYS.items()})
    requested = frontmatter_text(front, "requestedModel")
    effort = frontmatter_text(front, "effort")
    return UsageRecord(
        model=frontmatter_text(front, "aiModel"),
        alias=requested if requested in get_all_aliases() else None,
        profile=frontmatter_text(front, "aiProfile"),
        effort=effort,
        turns=_int(path, front, KEY_TURNS),
        duration_seconds=_float(path, front, KEY_DURATION_SECONDS),
        usage=tokens,
        cost_usd=_float(path, front, KEY_COST_USD),
        cost_basis=_basis(path, front),
    )


def frontmatter_text(front: Mapping[str, object], key: str) -> str | None:
    value = front.get(key)
    return None if value is None else str(value)


def _int(path: Path, front: Mapping[str, object], key: str) -> int | None:
    value = front.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        _warn(path, key, value)
        return None
    return value


def _float(path: Path, front: Mapping[str, object], key: str) -> float | None:
    value = front.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        _warn(path, key, value)
        return None
    return float(value)


def _basis(path: Path, front: Mapping[str, object]) -> CostBasis | None:
    value = front.get(KEY_COST_BASIS)
    if value is None:
        return None
    if value in {basis.value for basis in CostBasis}:
        return CostBasis(str(value))
    _warn(path, KEY_COST_BASIS, value)
    return None


def _warn(path: Path, key: str, value: object) -> None:
    _logger.warning("artifact %s: frontmatter %s is malformed: %.200r", path, key, value)
