"""Tests for recommend_thresholds report shape and no-mutation (T9/T10)."""

from __future__ import annotations

import hashlib
from collections.abc import Generator
from pathlib import Path

import pytest
import tomli_w

from squadron.metrology.calibration import recommend_thresholds
from squadron.metrology.calibration_models import RecommendationDirection, RecommendationReport
from squadron.metrology.levels import ArtifactLevel
from squadron.metrology.models import JudgeConfigId
from squadron.metrology.report_models import AgreementCell, AgreementReport, ExclusionSummary, GroupKey
from squadron.review.templates import ReviewTemplate, clear_registry, register_template

_FLOOR = 5
_GRADUATE_RATE = 0.9
_TIGHTEN_RATE = 0.6


@pytest.fixture(autouse=True)
def _clear_template_registry() -> Generator[None]:  # pyright: ignore[reportUnusedFunction]
    clear_registry()
    yield
    clear_registry()


def _register(name: str) -> None:
    register_template(
        ReviewTemplate(
            name=name,
            description="Example judge template",
            system_prompt="You are a judge.",
            allowed_tools=[],
            permission_mode="default",
            setting_sources=None,
            required_inputs=[],
            optional_inputs=[],
            model="minimax/minimax-m2.7",
            prompt_template="Judge this: {input}",
            judge={"pass_floor": 78, "concerns_floor": 55},
        )
    )


def _cell(
    *,
    template_name: str = "judge.slice-vs-arch",
    model: str = "minimax/minimax-m2.7",
    template_content_hash: str | None = "a" * 64,
    artifact_level: ArtifactLevel = ArtifactLevel.SLICE_DESIGN_VS_ARCH,
    n: int = 10,
    match_rate: float = 0.95,
    below_floor: bool = False,
) -> AgreementCell:
    return AgreementCell(
        group=GroupKey(
            artifact_level=artifact_level,
            judge_config=JudgeConfigId(
                template_name=template_name,
                model=model,
                template_content_hash=template_content_hash,
            ),
        ),
        n=n,
        match_rate=match_rate,
        below_floor=below_floor,
    )


def _recommend(agreement: AgreementReport) -> RecommendationReport:
    return recommend_thresholds(
        agreement, floor=_FLOOR, graduate_rate=_GRADUATE_RATE, tighten_rate=_TIGHTEN_RATE
    )


class TestRecommendThresholds:
    def test_multi_cell_yields_one_recommendation_per_cell(self) -> None:
        _register("judge.slice-vs-arch")
        _register("judge.tasks-vs-slice")
        agreement = AgreementReport(
            cells=[
                _cell(template_name="judge.slice-vs-arch", model="model-a"),
                _cell(
                    template_name="judge.tasks-vs-slice",
                    model="model-b",
                    artifact_level=ArtifactLevel.TASKS_VS_SLICE,
                    match_rate=0.5,
                ),
            ],
            excluded=ExclusionSummary(total_excluded=0, stale_judge_result=0, unversioned=0),
        )
        report = _recommend(agreement)
        assert len(report.cells) == 2

    def test_every_recommendation_has_non_empty_model_dimension_note(self) -> None:
        _register("judge.slice-vs-arch")
        agreement = AgreementReport(
            cells=[_cell()],
            excluded=ExclusionSummary(total_excluded=0, stale_judge_result=0, unversioned=0),
        )
        report = _recommend(agreement)
        for recommendation in report.cells:
            assert recommendation.target.model_dimension_note.strip() != ""

    def test_unregistered_template_target_current_is_none_no_exception(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        # Deliberately do not register a template for this cell.
        agreement = AgreementReport(
            cells=[_cell(template_name="judge.not-registered")],
            excluded=ExclusionSummary(total_excluded=0, stale_judge_result=0, unversioned=0),
        )
        report = _recommend(agreement)
        assert len(report.cells) == 1
        assert report.cells[0].target.current is None
        assert any(
            "judge.not-registered" in record.message and record.levelno == 30
            for record in caplog.records
        )

    def test_empty_agreement_report_yields_empty_recommendation_report(self) -> None:
        agreement = AgreementReport(
            cells=[],
            excluded=ExclusionSummary(total_excluded=0, stale_judge_result=0, unversioned=0),
        )
        report = _recommend(agreement)
        assert report.cells == []
        assert report.floor_applied == _FLOOR

    def test_excluded_summary_passed_through_verbatim(self) -> None:
        excluded = ExclusionSummary(total_excluded=3, stale_judge_result=2, unversioned=1)
        agreement = AgreementReport(cells=[], excluded=excluded)
        report = _recommend(agreement)
        assert report.excluded == excluded

    def test_unversioned_cell_never_graduates(self) -> None:
        _register("judge.slice-vs-arch")
        agreement = AgreementReport(
            cells=[_cell(template_content_hash=None, n=1000, match_rate=0.99)],
            excluded=ExclusionSummary(total_excluded=0, stale_judge_result=0, unversioned=1),
        )
        report = _recommend(agreement)
        assert report.cells[0].direction == RecommendationDirection.INSUFFICIENT_EVIDENCE


class TestNoMutation:
    def test_recommend_thresholds_does_not_touch_disk(self, tmp_path: Path) -> None:
        _register("judge.slice-vs-arch")

        template_yaml = tmp_path / "judge-slice-vs-arch.yaml"
        template_yaml.write_text("name: judge.slice-vs-arch\npass_floor: 78\n", encoding="utf-8")

        config_toml = tmp_path / ".squadron.toml"
        with open(config_toml, "wb") as handle:
            tomli_w.dump({"metrology.min_evidence_n": 5}, handle)

        store_dir = tmp_path / "store"
        store_dir.mkdir()
        (store_dir / "record-0001.json").write_text('{"schema_version": 1}', encoding="utf-8")

        def _snapshot() -> dict[str, bytes]:
            return {
                str(path): path.read_bytes() for path in sorted(tmp_path.rglob("*")) if path.is_file()
            }

        def _hashes(snapshot: dict[str, bytes]) -> dict[str, str]:
            return {key: hashlib.sha256(value).hexdigest() for key, value in snapshot.items()}

        before = _hashes(_snapshot())

        agreement = AgreementReport(
            cells=[_cell()],
            excluded=ExclusionSummary(total_excluded=0, stale_judge_result=0, unversioned=0),
        )
        _recommend(agreement)

        after = _hashes(_snapshot())
        assert before == after
