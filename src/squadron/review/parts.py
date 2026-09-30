"""Split-review parts: how one review becomes N, and how N verdicts become one.

A slice whose task breakdown is split across files (``-1.md``, ``-2.md``, ...)
is reviewed once per file. Both callers — CLI ``sq review tasks`` and the
pipeline ``review:`` action — take part naming and verdict folding from here,
so the artifacts they write and the verdict they report cannot drift apart.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from squadron.review.models import Verdict

#: Fold order, best to worst. UNKNOWN outranks PASS and CONCERNS: a part nobody
#: could read must never let the whole review pass. FAIL outranks UNKNOWN: a
#: definite FAIL must not hide behind an unreadable part (#176).
_VERDICT_RANK: dict[Verdict, int] = {
    verdict: rank
    for rank, verdict in enumerate((Verdict.PASS, Verdict.CONCERNS, Verdict.UNKNOWN, Verdict.FAIL))
}


@dataclass(frozen=True)
class ReviewPart:
    """One file to review and the suffix its artifact is saved under."""

    input_path: str
    name_suffix: str | None


def review_parts(input_paths: list[str]) -> list[ReviewPart]:
    """One part per path; a lone path keeps the unsuffixed artifact name.

    Two or more paths get ``part-1`` .. ``part-N`` in order. This is the only
    place that spells the ``part-N`` suffix.

    Raises:
        ValueError: If ``input_paths`` is empty — there is nothing to review.
    """
    if not input_paths:
        raise ValueError("review_parts: no input paths to review")
    if len(input_paths) == 1:
        return [ReviewPart(input_paths[0], None)]
    return [ReviewPart(path, f"part-{index}") for index, path in enumerate(input_paths, 1)]


def worst_verdict(verdicts: Iterable[str]) -> str:
    """The worst of ``verdicts`` by PASS < CONCERNS < UNKNOWN < FAIL.

    Ties return the first occurrence.

    Raises:
        ValueError: If ``verdicts`` is empty or holds a value outside ``Verdict``.
    """
    worst: str | None = None
    worst_rank = -1
    for value in verdicts:
        rank = _VERDICT_RANK[Verdict(value)]  # Verdict() raises on an unknown value
        if rank > worst_rank:
            worst, worst_rank = value, rank
    if worst is None:
        raise ValueError("worst_verdict: no verdicts to fold")
    return worst
