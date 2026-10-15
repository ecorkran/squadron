"""Provider-neutral token usage, per-run telemetry, and usage records (slices 931 D8, 175).

A leaf module: standard library only, so any layer can import it without a cycle. The
OpenAI wire format lives in ``providers/openai/usage.py`` and the SDK one in
``providers/sdk/usage.py``; this module holds only the shapes every provider maps onto.

``None`` means "not reported" throughout, and survives summing unless some turn reported
a value — a backend that omits a field is never recorded as 0.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import cast


def add_optional(total: int | None, value: int | None) -> int | None:
    """Sum two per-turn counts, keeping ``None`` only when neither turn reported."""
    if value is None:
        return total
    return (total or 0) + value


def add_optional_float(total: float | None, value: float | None) -> float | None:
    """``add_optional`` for floats (costs): ``None`` only when neither side reported."""
    if value is None:
        return total
    return (total or 0.0) + value


@dataclass(frozen=True)
class TokenUsage:
    """Token counts for one turn or a whole run; each ``None`` when not reported (175 D1).

    ``cached`` and ``cache_write`` are subsets of ``prompt``; ``reasoning`` is a subset
    of ``completion``.
    """

    prompt: int | None = None  # all input, incl. cached and cache_write
    cached: int | None = None  # read from cache
    cache_write: int | None = None  # written to cache
    completion: int | None = None  # all output, incl. reasoning
    reasoning: int | None = None

    def plus(self, other: TokenUsage) -> TokenUsage:
        """Field-wise ``add_optional`` sum of ``self`` and ``other``."""
        return TokenUsage(
            prompt=add_optional(self.prompt, other.prompt),
            cached=add_optional(self.cached, other.cached),
            cache_write=add_optional(self.cache_write, other.cache_write),
            completion=add_optional(self.completion, other.completion),
            reasoning=add_optional(self.reasoning, other.reasoning),
        )

    @property
    def reported(self) -> bool:
        """Did any field carry a value?"""
        values = (self.prompt, self.cached, self.cache_write, self.completion, self.reasoning)
        return any(v is not None for v in values)


@dataclass
class RunTelemetry:
    """What one ``handle_message`` call has cost so far: requests, reasoning, tokens, cost."""

    turns: int = 0
    reasoning_chars: int = 0
    usage: TokenUsage = field(default_factory=TokenUsage)
    cost_usd: float | None = None

    def fold_turn(self, *, reasoning_chars: int, usage: TokenUsage | None) -> None:
        """Count one sent request and add its reasoning and usage."""
        self.turns += 1
        self.reasoning_chars += reasoning_chars
        if usage is not None:
            self.usage = self.usage.plus(usage)

    def fold_result(
        self, *, turns: int | None, usage: TokenUsage | None, cost_usd: float | None
    ) -> None:
        """Add one whole-query result (SDK ``ResultMessage``): its turns, tokens, and cost."""
        if turns is not None:
            self.turns += turns
        if usage is not None:
            self.usage = self.usage.plus(usage)
        self.cost_usd = add_optional_float(self.cost_usd, cost_usd)

    def snapshot(self) -> RunTelemetry:
        """An independent copy; later folds into ``self`` do not reach it."""
        return replace(self)


class CostBasis(StrEnum):
    """Where a cost came from (175 D3)."""

    PROVIDER = "provider"
    ALIAS_PRICING = "alias_pricing"


_TOKEN_FIELDS = ("prompt", "cached", "cache_write", "completion", "reasoning")


@dataclass(frozen=True)
class UsageRecord:
    """What one LLM action spent, as persisted in ``ActionResult.metadata`` (175)."""

    model: str | None  # answering model when known, else requested
    alias: str | None
    profile: str | None
    effort: str | None  # sent, else None (D7)
    turns: int | None
    duration_seconds: float | None
    usage: TokenUsage
    cost_usd: float | None
    cost_basis: CostBasis | None
    partial: bool = False  # an interrupted turn's spend is missing (D5)

    def to_dict(self) -> dict[str, object]:
        """The persisted shape: tokens nested under ``tokens``; ``partial`` only when set."""
        out: dict[str, object] = {
            "model": self.model,
            "alias": self.alias,
            "profile": self.profile,
            "effort": self.effort,
            "turns": self.turns,
            "duration_seconds": self.duration_seconds,
            "tokens": {name: getattr(self.usage, name) for name in _TOKEN_FIELDS},
            "cost_usd": self.cost_usd,
            "cost_basis": None if self.cost_basis is None else self.cost_basis.value,
        }
        if self.partial:
            out["partial"] = True
        return out

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> UsageRecord:
        """Inverse of ``to_dict``; raises ``ValueError`` naming the first malformed key."""
        tokens = raw.get("tokens")
        token_map: Mapping[str, object] = {}
        if tokens is not None:
            if not isinstance(tokens, Mapping):
                raise ValueError(f"usage key 'tokens' is not a mapping: {tokens!r:.200}")
            token_map = cast("Mapping[str, object]", tokens)
        usage = TokenUsage(**{name: _opt_int(token_map, name) for name in _TOKEN_FIELDS})
        partial = raw.get("partial", False)
        if not isinstance(partial, bool):
            raise ValueError(f"usage key 'partial' is not a bool: {partial!r:.200}")
        return cls(
            model=_opt_str(raw, "model"),
            alias=_opt_str(raw, "alias"),
            profile=_opt_str(raw, "profile"),
            effort=_opt_str(raw, "effort"),
            turns=_opt_int(raw, "turns"),
            duration_seconds=_opt_float(raw, "duration_seconds"),
            usage=usage,
            cost_usd=_opt_float(raw, "cost_usd"),
            cost_basis=_opt_basis(raw),
            partial=partial,
        )


def _opt_str(raw: Mapping[str, object], key: str) -> str | None:
    value = raw.get(key)
    if value is None or isinstance(value, str):
        return value
    raise ValueError(f"usage key {key!r} is not a string: {value!r:.200}")


def _opt_int(raw: Mapping[str, object], key: str) -> int | None:
    value = raw.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"usage key {key!r} is not an int: {value!r:.200}")
    return value


def _opt_float(raw: Mapping[str, object], key: str) -> float | None:
    value = raw.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"usage key {key!r} is not a number: {value!r:.200}")
    return float(value)


def _opt_basis(raw: Mapping[str, object]) -> CostBasis | None:
    value = raw.get("cost_basis")
    if value is None:
        return None
    try:
        return CostBasis(value)
    except ValueError:
        raise ValueError(f"usage key 'cost_basis' has unknown value: {value!r:.200}") from None
