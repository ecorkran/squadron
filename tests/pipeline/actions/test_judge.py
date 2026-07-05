"""Tests for the judge enforcement layer: thresholds, resolution, enforcement."""

from __future__ import annotations

import pytest

from squadron.pipeline.actions.judge import (
    _DEFAULT_CONCERNS_FLOOR,
    _DEFAULT_PASS_FLOOR,
    JudgeThresholds,
    resolve_thresholds,
)
from squadron.review.models import Verdict


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
