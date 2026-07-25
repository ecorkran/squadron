"""Tests for report model round-trip and grouping-key semantics."""

from __future__ import annotations

from squadron.metrology.levels import ArtifactLevel
from squadron.metrology.models import JudgeConfigId
from squadron.metrology.report_models import (
    AgreementCell,
    AgreementReport,
    ArtifactKey,
    DispersionCell,
    DispersionReport,
    ExclusionSummary,
    GroupKey,
    TrendBucket,
    TrendReport,
)


def _judge_config(model: str = "minimax/minimax-m2.7") -> JudgeConfigId:
    return JudgeConfigId(template_name="judge.slice-vs-arch", model=model)


def _agreement_report() -> AgreementReport:
    cell = AgreementCell(
        group=GroupKey(
            artifact_level=ArtifactLevel.SLICE_DESIGN_VS_ARCH,
            judge_config=_judge_config(),
        ),
        n=5,
        match_rate=0.8,
        below_floor=False,
    )
    return AgreementReport(
        cells=[cell],
        excluded=ExclusionSummary(total_excluded=1, stale_judge_result=1, unversioned=0),
    )


def _dispersion_report() -> DispersionReport:
    cell = DispersionCell(
        artifact=ArtifactKey(
            project_id="github.com/manta/example-repo",
            source_document="project-documents/user/slices/500-slice.example.md",
            artifact_level=ArtifactLevel.SLICE_DESIGN_VS_ARCH,
        ),
        judge_configs=[_judge_config("model-a"), _judge_config("model-b")],
        n=2,
        disagreement_rate=0.5,
    )
    return DispersionReport(
        cells=[cell],
        excluded=ExclusionSummary(total_excluded=0, stale_judge_result=0, unversioned=0),
    )


def test_agreement_report_round_trips_through_json() -> None:
    report = _agreement_report()
    dumped = report.model_dump(mode="json")
    restored = AgreementReport.model_validate(dumped)
    assert restored == report


def test_dispersion_report_round_trips_through_json() -> None:
    report = _dispersion_report()
    dumped = report.model_dump(mode="json")
    restored = DispersionReport.model_validate(dumped)
    assert restored == report


def test_trend_report_round_trips_through_json() -> None:
    report = TrendReport(
        bucket="month",
        series=[
            TrendBucket(
                bucket_label="2026-07",
                agreement=_agreement_report(),
                dispersion=_dispersion_report(),
            )
        ],
    )
    dumped = report.model_dump(mode="json")
    restored = TrendReport.model_validate(dumped)
    assert restored == report


def test_exclusion_summary_counts_are_non_negative() -> None:
    summary = ExclusionSummary(total_excluded=3, stale_judge_result=2, unversioned=1)
    assert summary.total_excluded >= 0
    assert summary.stale_judge_result >= 0
    assert summary.unversioned >= 0


def test_agreement_and_dispersion_reports_always_carry_excluded() -> None:
    agreement = AgreementReport(
        cells=[], excluded=ExclusionSummary(total_excluded=0, stale_judge_result=0, unversioned=0)
    )
    dispersion = DispersionReport(
        cells=[], excluded=ExclusionSummary(total_excluded=0, stale_judge_result=0, unversioned=0)
    )
    assert agreement.excluded is not None
    assert dispersion.excluded is not None


def test_artifact_key_distinguishes_by_source_document() -> None:
    level = ArtifactLevel.SLICE_DESIGN_VS_ARCH
    key_a = ArtifactKey(
        project_id="github.com/manta/example-repo",
        source_document="project-documents/user/slices/500-slice.example.md",
        artifact_level=level,
    )
    key_b = ArtifactKey(
        project_id="github.com/manta/example-repo",
        source_document="project-documents/user/slices/501-slice.other.md",
        artifact_level=level,
    )
    key_a_again = key_a.model_copy()

    assert key_a != key_b
    # Suitable as a dict/group key: distinct artifacts hash to distinct
    # entries, equal artifacts collapse to one.
    grouped = {key_a.model_dump_json(): "a", key_b.model_dump_json(): "b"}
    assert len(grouped) == 2
    assert key_a.model_dump_json() == key_a_again.model_dump_json()
