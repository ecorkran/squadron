"""Tests for calibration/graduation model round-trip (T4)."""

from __future__ import annotations

from datetime import UTC, datetime

from squadron.metrology.calibration_models import (
    EvidenceSnapshot,
    GraduatedConfig,
    OfferTarget,
    RecommendationDirection,
    RecommendationReport,
    ThresholdRecommendation,
    ThresholdTarget,
)
from squadron.metrology.levels import ArtifactLevel
from squadron.metrology.models import JudgeConfigId
from squadron.metrology.report_models import ExclusionSummary, GroupKey
from squadron.pipeline.actions.judge import JudgeThresholds


def _judge_config(
    model: str = "minimax/minimax-m2.7", template_content_hash: str | None = "a" * 64
) -> JudgeConfigId:
    return JudgeConfigId(
        template_name="judge.slice-vs-arch",
        model=model,
        template_content_hash=template_content_hash,
    )


def _evidence() -> EvidenceSnapshot:
    return EvidenceSnapshot(n=10, match_rate=0.9, floor_applied=5, below_floor=False)


def _recommendation() -> ThresholdRecommendation:
    return ThresholdRecommendation(
        group=GroupKey(artifact_level=ArtifactLevel.SLICE_DESIGN_VS_ARCH, judge_config=_judge_config()),
        direction=RecommendationDirection.GRADUATE,
        evidence=_evidence(),
        target=ThresholdTarget(
            template_name="judge.slice-vs-arch",
            current=JudgeThresholds(pass_floor=78.0, concerns_floor=55.0),
            model_dimension_note=(
                "This recommendation holds for judge.slice-vs-arch paired with "
                "minimax/minimax-m2.7; config has no model dimension."
            ),
        ),
        rationale="n=10 >= floor=5, match_rate=0.9 >= graduate_rate",
    )


def test_threshold_recommendation_round_trips_through_json() -> None:
    recommendation = _recommendation()
    dumped = recommendation.model_dump(mode="json")
    restored = ThresholdRecommendation.model_validate(dumped)
    assert restored == recommendation


def test_recommendation_report_round_trips_and_excluded_always_present() -> None:
    report = RecommendationReport(
        cells=[_recommendation()],
        excluded=ExclusionSummary(total_excluded=1, stale_judge_result=0, unversioned=1),
        floor_applied=5,
    )
    dumped = report.model_dump(mode="json")
    restored = RecommendationReport.model_validate(dumped)
    assert restored == report
    assert restored.excluded is not None


def test_threshold_target_current_is_none_able_for_unregistered_template() -> None:
    target = ThresholdTarget(
        template_name="judge.no-longer-registered",
        current=None,
        model_dimension_note="Template is no longer registered; no current thresholds to show.",
    )
    dumped = target.model_dump(mode="json")
    restored = ThresholdTarget.model_validate(dumped)
    assert restored.current is None
    assert restored == target


def test_graduated_config_round_trips_and_carries_template_content_hash() -> None:
    graduated = GraduatedConfig(
        judge_config=_judge_config(template_content_hash="b" * 64),
        artifact_level=ArtifactLevel.SLICE_DESIGN_VS_ARCH,
        evidence=_evidence(),
        graduated_at=datetime(2026, 7, 25, tzinfo=UTC),
    )
    dumped = graduated.model_dump(mode="json")
    restored = GraduatedConfig.model_validate(dumped)
    assert restored == graduated
    # Version-scoping: the field must exist and survive the round-trip, not
    # just template_name/model.
    assert restored.judge_config.template_content_hash == "b" * 64


def test_offer_target_round_trips_through_json() -> None:
    offer = OfferTarget(
        review_path="project-documents/user/reviews/500-review.judge.slice-vs-arch.example.md",
        judge_config=_judge_config(),
        reason="residual-sampling",
    )
    dumped = offer.model_dump(mode="json")
    restored = OfferTarget.model_validate(dumped)
    assert restored == offer
