"""Judge enforcement layer: verdict derivation, threshold resolution, provenance."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

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
