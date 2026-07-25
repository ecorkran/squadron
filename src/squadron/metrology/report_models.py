"""Typed report shapes — the stable interface 322 consumes.

Pydantic models, not console text: ``--json`` emits these verbatim. Every
report carries an ``ExclusionSummary`` so exclusions are always visible
rather than mistaken for absence of data.
"""

from __future__ import annotations

from pydantic import BaseModel

from squadron.metrology.levels import ArtifactLevel
from squadron.metrology.models import JudgeConfigId


class GroupKey(BaseModel):
    """Agreement/trend group key: artifact level x judge configuration."""

    artifact_level: ArtifactLevel
    judge_config: JudgeConfigId


class AgreementCell(BaseModel):
    """One agreement measurement for one ``GroupKey``."""

    group: GroupKey
    n: int
    match_rate: float
    below_floor: bool


class ArtifactKey(BaseModel):
    """Dispersion's group key: the artifact identity, not a review-file
    instance. Two judge configs grading the same artifact write two
    different review files (two different ``result_ref``s) but share one
    ``ArtifactKey``."""

    project_id: str
    source_document: str
    artifact_level: ArtifactLevel


class DispersionCell(BaseModel):
    """One dispersion measurement for one artifact across distinct judge
    configurations."""

    artifact: ArtifactKey
    judge_configs: list[JudgeConfigId]
    n: int
    disagreement_rate: float


class ExclusionSummary(BaseModel):
    """Counts of samples excluded from a report, never silent."""

    total_excluded: int
    stale_judge_result: int
    unversioned: int
    missing_source_document: int = 0


class AgreementReport(BaseModel):
    """Per-level / per-config agreement, never a single blended number."""

    cells: list[AgreementCell]
    excluded: ExclusionSummary


class DispersionReport(BaseModel):
    """Per-artifact dispersion across distinct judge configurations."""

    cells: list[DispersionCell]
    excluded: ExclusionSummary


class TrendBucket(BaseModel):
    """One time-bucketed slice of the agreement/dispersion figures."""

    bucket_label: str
    agreement: AgreementReport
    dispersion: DispersionReport


class TrendReport(BaseModel):
    """Agreement/dispersion figures bucketed over time, oldest first."""

    bucket: str
    series: list[TrendBucket]
