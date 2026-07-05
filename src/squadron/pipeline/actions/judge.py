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
