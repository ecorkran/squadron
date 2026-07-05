"""Tests for the judge enforcement layer: thresholds, resolution, enforcement."""

from __future__ import annotations

import logging

import pytest

from squadron.pipeline.actions.judge import (
    _DEFAULT_CONCERNS_FLOOR,
    _DEFAULT_PASS_FLOOR,
    JudgeThresholds,
    enforce_judge,
    resolve_thresholds,
)
from squadron.review.models import ReviewResult, Verdict


def _make_result(score: float | None, verdict: Verdict = Verdict.UNKNOWN) -> ReviewResult:
    return ReviewResult(
        verdict=verdict,
        findings=[],
        raw_output="",
        template_name="judge.test",
        input_files={},
        score=score,
    )


class TestDeriveVerdict:
    """Test JudgeThresholds.derive_verdict band boundaries."""

    @pytest.mark.parametrize(
        ("score", "expected"),
        [
            (100.0, Verdict.PASS.value),
            (75.0, Verdict.PASS.value),
            (74.9, Verdict.CONCERNS.value),
            (60.0, Verdict.CONCERNS.value),
            (50.0, Verdict.CONCERNS.value),
            (49.9, Verdict.FAIL.value),
            (0.0, Verdict.FAIL.value),
        ],
    )
    def test_band_boundaries(self, score: float, expected: str) -> None:
        thresholds = JudgeThresholds(pass_floor=75.0, concerns_floor=50.0)
        assert thresholds.derive_verdict(score) == expected


class TestResolveThresholds:
    """Test resolve_thresholds per-key merge precedence."""

    def test_all_defaults(self) -> None:
        t = resolve_thresholds(None, None)
        assert t.pass_floor == _DEFAULT_PASS_FLOOR
        assert t.concerns_floor == _DEFAULT_CONCERNS_FLOOR

    def test_template_partial_override(self) -> None:
        t = resolve_thresholds({"concerns_floor": 40}, None)
        assert t.pass_floor == _DEFAULT_PASS_FLOOR
        assert t.concerns_floor == 40.0

    def test_step_override_one_key_template_supplies_other(self) -> None:
        t = resolve_thresholds({"concerns_floor": 45}, {"pass_floor": 80})
        assert t.pass_floor == 80.0
        assert t.concerns_floor == 45.0

    def test_step_override_wins_over_template(self) -> None:
        t = resolve_thresholds({"pass_floor": 70, "concerns_floor": 45}, {"pass_floor": 80})
        assert t.pass_floor == 80.0
        assert t.concerns_floor == 45.0

    def test_int_valued_yaml_inputs_coerce_to_float(self) -> None:
        t = resolve_thresholds({"pass_floor": 80}, None)
        assert t.pass_floor == 80.0
        assert isinstance(t.pass_floor, float)


class TestEnforceJudge:
    """Test enforce_judge failure modes and the score-wins-over-verdict contract."""

    @pytest.fixture
    def thresholds(self) -> JudgeThresholds:
        return JudgeThresholds(pass_floor=75.0, concerns_floor=50.0)

    @pytest.fixture
    def logger(self) -> logging.Logger:
        return logging.getLogger("test_enforce_judge")

    def test_score_none_yields_unknown_and_warning(
        self, thresholds: JudgeThresholds, logger: logging.Logger, caplog: pytest.LogCaptureFixture
    ) -> None:
        result = _make_result(score=None)
        with caplog.at_level(logging.WARNING):
            verdict, provenance = enforce_judge(result, thresholds, "judge.test", logger)
        assert verdict == "UNKNOWN"
        assert provenance == "judge"
        assert any(r.levelno >= logging.WARNING for r in caplog.records)

    def test_score_below_range_yields_unknown_and_warning(
        self, thresholds: JudgeThresholds, logger: logging.Logger, caplog: pytest.LogCaptureFixture
    ) -> None:
        result = _make_result(score=-3.0)
        with caplog.at_level(logging.WARNING):
            verdict, provenance = enforce_judge(result, thresholds, "judge.test", logger)
        assert verdict == "UNKNOWN"
        assert provenance == "judge"
        assert any(r.levelno >= logging.WARNING for r in caplog.records)

    def test_score_above_range_yields_unknown_and_warning(
        self, thresholds: JudgeThresholds, logger: logging.Logger, caplog: pytest.LogCaptureFixture
    ) -> None:
        result = _make_result(score=150.0)
        with caplog.at_level(logging.WARNING):
            verdict, provenance = enforce_judge(result, thresholds, "judge.test", logger)
        assert verdict == "UNKNOWN"
        assert provenance == "judge"
        assert any(r.levelno >= logging.WARNING for r in caplog.records)

    @pytest.mark.parametrize(
        ("score", "expected"),
        [(80.0, "PASS"), (60.0, "CONCERNS"), (30.0, "FAIL")],
    )
    def test_valid_score_derives_verdict_with_no_warning(
        self,
        score: float,
        expected: str,
        thresholds: JudgeThresholds,
        logger: logging.Logger,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        result = _make_result(score=score)
        with caplog.at_level(logging.WARNING):
            verdict, provenance = enforce_judge(result, thresholds, "judge.test", logger)
        assert verdict == expected
        assert provenance == "judge"
        assert not any(r.levelno >= logging.WARNING for r in caplog.records)

    def test_score_wins_over_mismatched_parsed_verdict(
        self, thresholds: JudgeThresholds, logger: logging.Logger
    ) -> None:
        result = _make_result(score=95.0, verdict=Verdict.FAIL)
        verdict, provenance = enforce_judge(result, thresholds, "judge.test", logger)
        assert verdict == "PASS"
        assert provenance == "judge"
