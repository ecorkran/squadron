"""Judge enforcement layer: verdict derivation, threshold resolution, provenance."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from squadron.review.models import ReviewResult

_DEFAULT_PASS_FLOOR = 75.0
_DEFAULT_CONCERNS_FLOOR = 50.0


class Provenance(StrEnum):
    """Origin of a review action's verdict."""

    JUDGE = "judge"
    REVIEW = "review"


@dataclass
class JudgeThresholds:
    """Resolved pass/concerns score floors for a judge template."""

    pass_floor: float
    concerns_floor: float

    def derive_verdict(self, score: float) -> str:
        """Derive a Verdict string from a score using this threshold's bands."""
        if score >= self.pass_floor:
            return "PASS"
        if score >= self.concerns_floor:
            return "CONCERNS"
        return "FAIL"


def resolve_thresholds(
    template_judge: dict[str, object] | None,
    step_override: dict[str, object] | None,
) -> JudgeThresholds:
    """Merge threshold values per-key: step override → template default → module constant."""
    template_judge = template_judge or {}
    step_override = step_override or {}

    pass_floor = step_override.get("pass_floor", template_judge.get("pass_floor", _DEFAULT_PASS_FLOOR))
    concerns_floor = step_override.get(
        "concerns_floor", template_judge.get("concerns_floor", _DEFAULT_CONCERNS_FLOOR)
    )

    return JudgeThresholds(
        pass_floor=float(pass_floor),  # type: ignore[arg-type]
        concerns_floor=float(concerns_floor),  # type: ignore[arg-type]
    )


def enforce_judge(
    result: ReviewResult,
    thresholds: JudgeThresholds,
    template_name: str,
    logger: logging.Logger,
) -> tuple[str, str]:
    """Derive a judge verdict and provenance from a review result's score.

    Ignores result.verdict entirely — the verdict is always threshold-derived
    from the score, never a raw model opinion.
    """
    score = result.score

    if score is None:
        logger.warning("Judge template '%s' produced no score; verdict=UNKNOWN", template_name)
        return "UNKNOWN", Provenance.JUDGE

    if score < 0 or score > 100:
        logger.warning(
            "Judge template '%s' produced out-of-range score %s; verdict=UNKNOWN",
            template_name,
            score,
        )
        return "UNKNOWN", Provenance.JUDGE

    return thresholds.derive_verdict(score), Provenance.JUDGE
