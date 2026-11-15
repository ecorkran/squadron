"""A pair of configs under the paired statistic, and how its verdict reads (slices 425, 426).

The fix-case and slice-case tables and the pairwise section all report a mean difference with
an interval and a ``PairVerdict``, so they share this one model and this one wording.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from squadron.metrology.grade_models import PairVerdict


class PairRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    label_a: str
    label_b: str
    n_cases: int
    mean_difference: float
    low: float | None
    high: float | None
    verdict: PairVerdict


def verdict_text(pair: PairRow) -> str:
    """The verdict of a pair with enough cases to have one (not ``TOO_FEW_CASES``)."""
    return {
        PairVerdict.A_AHEAD: f"{pair.label_a} ahead",
        PairVerdict.B_AHEAD: f"{pair.label_b} ahead",
        PairVerdict.NOT_DISTINGUISHABLE: "not distinguishable",
    }[pair.verdict]
