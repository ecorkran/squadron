"""Gate action — reduces a judge verdict and a review verdict to one verdict."""

from __future__ import annotations

from enum import IntEnum


class _Severity(IntEnum):
    """Verdict severity ranking, most severe first (highest value = most severe).

    UNKNOWN is ranked most severe deliberately: a judgment that could not be
    rendered must dominate a passing leg, never be masked by it (no-silent-pass).
    """

    PASS = 0
    CONCERNS = 1
    FAIL = 2
    UNKNOWN = 3


def _normalize(verdict: str | None) -> str:
    """Map a None verdict to UNKNOWN before ranking (fail-closed, F001)."""
    return verdict if verdict is not None else "UNKNOWN"


def reduce_verdicts(a: str | None, b: str | None) -> str:
    """Reduce two verdicts to the more severe of the pair (most-severe-wins).

    None is normalized to UNKNOWN before ranking, so a verdict-less leg
    dominates rather than vanishing. Pure function: no I/O, no logging —
    callers that need to observe a None leg (e.g. GateAction) log it
    themselves before calling this.
    """
    severity_a = _Severity[_normalize(a)]
    severity_b = _Severity[_normalize(b)]
    return max(severity_a, severity_b).name
