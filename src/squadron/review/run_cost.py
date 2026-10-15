"""What a review run cost — turns, tokens, wall-clock — in its three renderings (slice 931 D10).

A successful review and a provider failure both carry these facts, from a ``ReviewResult``
or from the ``ProviderError`` that ended the run. Rendering lives here once so the
frontmatter keys, digest lines, and JSON keys cannot drift between the two artifacts.

``None`` means "not reported" everywhere: frontmatter omits the key, the digest prints the
sentinel every other digest line uses, JSON emits null. A value is never fabricated into 0.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from squadron.core.usage import CostBasis, TokenUsage, format_usd
from squadron.providers.errors import ProviderError

#: The Run Digest's one sentinel for a fact nobody produced; persistence renders it too.
NOT_COMPUTED = "not computed"
#: The digest's wording for a run with no known cost (slice 175 D3): never $0.
COST_NOT_REPORTED = "not reported"


@dataclass(frozen=True)
class RunCost:
    turns: int | None = None
    usage: TokenUsage = field(default_factory=TokenUsage)
    duration_seconds: float | None = None
    cost_usd: float | None = None
    cost_basis: CostBasis | None = None

    @classmethod
    def from_error(cls, exc: ProviderError) -> RunCost:
        """What the run cost before ``exc`` ended it; the agent and review_client stamp these."""
        telemetry = exc.telemetry
        if telemetry is None:
            return cls(
                duration_seconds=exc.duration_seconds,
                cost_usd=exc.cost_usd,
                cost_basis=exc.cost_basis,
            )
        return cls(
            turns=telemetry.turns,
            usage=telemetry.usage,
            duration_seconds=exc.duration_seconds,
            cost_usd=exc.cost_usd,
            cost_basis=exc.cost_basis,
        )

    def frontmatter_lines(self) -> list[str]:
        """Each key only when it has a value (D10 table)."""
        keyed: list[tuple[str, object | None]] = [
            ("turns", self.turns),
            ("promptTokens", self.usage.prompt),
            ("cachedTokens", self.usage.cached),
            ("cacheWriteTokens", self.usage.cache_write),
            ("completionTokens", self.usage.completion),
            ("reasoningTokens", self.usage.reasoning),
            ("durationSeconds", self._duration()),
            ("costUsd", None if self.cost_usd is None else round(self.cost_usd, 6)),
            ("costBasis", None if self.cost_basis is None else self.cost_basis.value),
        ]
        return [f"{key}: {value}" for key, value in keyed if value is not None]

    def digest_lines(self) -> list[str]:
        """Always rendered, so every artifact says what it knows and what it does not."""
        usage = self.usage
        counts = (usage.prompt, usage.cached, usage.cache_write, usage.completion, usage.reasoning)
        tokens = " / ".join(_optional(v) for v in counts)
        duration = self._duration()
        return [
            f"- Turns: {_optional(self.turns)}",
            f"- Tokens — prompt / cached / cache write / completion / reasoning: {tokens}",
            f"- Duration: {NOT_COMPUTED if duration is None else f'{duration} s'}",
            f"- Cost: {self._cost()}",
        ]

    def json_fields(self) -> dict[str, object]:
        """Always present, null when not reported (stop_reason's convention)."""
        return {
            "turns": self.turns,
            "prompt_tokens": self.usage.prompt,
            "cached_tokens": self.usage.cached,
            "cache_write_tokens": self.usage.cache_write,
            "completion_tokens": self.usage.completion,
            "reasoning_tokens": self.usage.reasoning,
            "duration_seconds": self.duration_seconds,
            "cost_usd": self.cost_usd,
            "cost_basis": None if self.cost_basis is None else self.cost_basis.value,
        }

    def _cost(self) -> str:
        if self.cost_usd is None:
            return COST_NOT_REPORTED
        basis = "" if self.cost_basis is None else f" ({self.cost_basis.value})"
        return f"{format_usd(self.cost_usd)}{basis}"

    def _duration(self) -> str | None:
        return None if self.duration_seconds is None else f"{self.duration_seconds:.1f}"


def _optional(value: int | None) -> str:
    return NOT_COMPUTED if value is None else str(value)
