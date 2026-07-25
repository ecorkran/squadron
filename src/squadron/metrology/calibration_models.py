"""Typed calibration/graduation output shapes — the stable interface 322 emits.

Pydantic models, not console text: ``--json`` emits these verbatim. Mirrors
``report_models.py``'s pattern (321). A ``ThresholdRecommendation`` is
advisory only — a direction and the evidence for it, never a computed
numeric floor the operator must accept.

``EvidenceSnapshot`` and ``GraduatedConfig`` live in ``models.py``, not
here: ``GraduatedConfig`` is a ``MetrologyRecord`` envelope payload
(alongside ``SampleVerdict``), and defining it there avoids a circular
import between the envelope and this module.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel

from squadron.metrology.models import EvidenceSnapshot, GraduatedConfig, JudgeConfigId
from squadron.metrology.report_models import ExclusionSummary, GroupKey
from squadron.pipeline.actions.judge import JudgeThresholds

__all__ = [
    "EvidenceSnapshot",
    "GraduatedConfig",
    "OfferTarget",
    "RecommendationDirection",
    "RecommendationReport",
    "ThresholdRecommendation",
    "ThresholdTarget",
]


class RecommendationDirection(StrEnum):
    """The advisory direction a calibration cell resolves to.

    ``GRADUATE`` and ``HOLD`` are floor-gated (loosening requires evidence);
    ``TIGHTEN`` is not (a weak judge is worth flagging on thin evidence);
    ``INSUFFICIENT_EVIDENCE`` covers both the below-floor and unversioned
    refusal cases.
    """

    GRADUATE = "graduate"
    HOLD = "hold"
    TIGHTEN = "tighten"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class ThresholdTarget(BaseModel):
    """Where a recommendation would apply against 300's config surface.

    ``current`` is absent (``None``) when the template is no longer
    registered — never fabricated. ``model_dimension_note`` is mandatory:
    every recommendation states that it is bound to this template paired
    with this model, and that config has no model dimension.
    """

    template_name: str
    current: JudgeThresholds | None
    model_dimension_note: str

    model_config = {"arbitrary_types_allowed": True}


class ThresholdRecommendation(BaseModel):
    """One advisory recommendation for one ``(ArtifactLevel, JudgeConfigId)`` cell."""

    group: GroupKey
    direction: RecommendationDirection
    evidence: EvidenceSnapshot
    target: ThresholdTarget
    rationale: str


class RecommendationReport(BaseModel):
    """Per-cell advisory recommendations, never a single blended verdict."""

    cells: list[ThresholdRecommendation]
    excluded: ExclusionSummary
    floor_applied: int


class OfferTarget(BaseModel):
    """One residual-sampling offer: a judge result worth a spot-check."""

    review_path: str
    judge_config: JudgeConfigId
    reason: Literal["residual-sampling"] = "residual-sampling"
