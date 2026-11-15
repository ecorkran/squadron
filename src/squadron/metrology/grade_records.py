"""Grade and sample-size records (slice 425 D10, D15, Database Schema).

Split from ``grade_models.py`` (the parts a record is made of) so each stays near the file
bound. A grade has a result or an absence, never both; an absence's class comes from
``GRADE_ABSENCE_CLASS`` and nowhere else.
"""

from __future__ import annotations

from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from squadron.metrology.benchmark_replay_enums import AbsenceClass
from squadron.metrology.floor_stat import FloorStat
from squadron.metrology.grade_models import (
    GRADE_ABSENCE_CLASS,
    GradeAbsence,
    GradeResult,
    GraderIdentity,
    SnapshotRef,
    check_detail,
)


def _check_result_or_absence(
    result: GradeResult | None, absence: GradeAbsence | None, detail: str | None
) -> None:
    if (result is None) == (absence is None):
        raise ValueError("a grade has a result or an absence, exactly one of the two")
    check_detail(detail)


class ReferenceGrade(BaseModel):
    """A case's reference graded like a replay: the baseline, the floor and the pass.

    It carries no benchmark id: it belongs to the case and every benchmark of the case
    shares it. ``environment_digest`` is the digest it was planned for. The baseline fields
    are ``None`` only when the grade ended before the baseline was taken.
    """

    model_config = ConfigDict(frozen=True)

    case_id: str
    grader: GraderIdentity
    environment_digest: str
    result: GradeResult | None
    absence: GradeAbsence | None
    detail: str | None
    #: ``nodes`` sidecar of the start tree's collected node ids.
    baseline_nodes: str | None
    baseline_snapshot: SnapshotRef | None
    baseline_lint_total: int | None
    baseline_type_total: int | None
    review_floor: FloorStat | None
    grading_cost_usd: float | None
    wall_seconds: float
    created_at: datetime

    @model_validator(mode="after")
    def _valid(self) -> Self:
        _check_result_or_absence(self.result, self.absence, self.detail)
        if self.result is not None and (self.baseline_nodes is None or self.baseline_snapshot is None):
            raise ValueError("a reference grade with a result must carry its baseline")
        return self


class ImplementationGrade(BaseModel):
    """One replay graded (D1)."""

    model_config = ConfigDict(frozen=True)

    replay_id: str
    benchmark_id: str
    case_id: str
    grader: GraderIdentity
    #: The grade sandbox's digest; ``None`` when that environment did not resolve.
    environment_digest: str | None
    result: GradeResult | None
    absence: GradeAbsence | None
    absence_class: AbsenceClass | None
    detail: str | None
    grading_cost_usd: float | None
    wall_seconds: float
    created_at: datetime

    @model_validator(mode="after")
    def _valid(self) -> Self:
        _check_result_or_absence(self.result, self.absence, self.detail)
        expected = None if self.absence is None else GRADE_ABSENCE_CLASS[self.absence]
        if self.absence_class != expected:
            raise ValueError(f"absence_class must be {expected} for absence {self.absence}")
        return self


class CasesNeeded(BaseModel):
    """Cases needed to reach the target difference at *samples* samples per case."""

    model_config = ConfigDict(frozen=True)

    samples: int
    cases: int


class PairEstimate(BaseModel):
    """Measured variance of one config pair and what it implies (D15)."""

    model_config = ConfigDict(frozen=True)

    config_a: str
    config_b: str
    within_case_variance: float
    between_case_variance: float
    #: The minimum detectable difference at the run's own n cases and k samples.
    mdd_now: float
    cases_needed: tuple[CasesNeeded, ...]


class SampleSizeEstimate(BaseModel):
    """The benchmark's one measured sample-count estimate, overwritten at each grade run."""

    model_config = ConfigDict(frozen=True)

    benchmark_id: str
    case_set: str
    case_set_version: int
    grader_digest: str
    n_cases: int
    samples: int
    pairs: tuple[PairEstimate, ...]
    created_at: datetime
