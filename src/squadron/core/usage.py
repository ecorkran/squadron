"""Provider-neutral token usage and per-run telemetry (slice 931 D8).

A leaf module: standard library only, so any layer can import it without a cycle. The
OpenAI wire format lives in ``providers/openai/usage.py``; this module holds only the
shapes every provider maps onto.

``None`` means "not reported" throughout, and survives summing unless some turn reported
a value — a backend that omits a field is never recorded as 0.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace


def add_optional(total: int | None, value: int | None) -> int | None:
    """Sum two per-turn counts, keeping ``None`` only when neither turn reported."""
    if value is None:
        return total
    return (total or 0) + value


@dataclass(frozen=True)
class TokenUsage:
    """Token counts for one turn or a whole run; each ``None`` when not reported."""

    prompt: int | None = None
    cached: int | None = None
    completion: int | None = None
    reasoning: int | None = None

    def plus(self, other: TokenUsage) -> TokenUsage:
        """Field-wise ``add_optional`` sum of ``self`` and ``other``."""
        return TokenUsage(
            prompt=add_optional(self.prompt, other.prompt),
            cached=add_optional(self.cached, other.cached),
            completion=add_optional(self.completion, other.completion),
            reasoning=add_optional(self.reasoning, other.reasoning),
        )

    @property
    def reported(self) -> bool:
        """Did any field carry a value?"""
        return any(v is not None for v in (self.prompt, self.cached, self.completion, self.reasoning))


@dataclass
class RunTelemetry:
    """What one ``handle_message`` call has cost so far: requests sent, reasoning, tokens."""

    turns: int = 0
    reasoning_chars: int = 0
    usage: TokenUsage = field(default_factory=TokenUsage)

    def fold_turn(self, *, reasoning_chars: int, usage: TokenUsage | None) -> None:
        """Count one sent request and add its reasoning and usage."""
        self.turns += 1
        self.reasoning_chars += reasoning_chars
        if usage is not None:
            self.usage = self.usage.plus(usage)

    def snapshot(self) -> RunTelemetry:
        """An independent copy; later folds into ``self`` do not reach it."""
        return replace(self)
