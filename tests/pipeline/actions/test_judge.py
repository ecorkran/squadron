"""Tests for the judge enforcement layer: thresholds, resolution, enforcement."""

from __future__ import annotations

import pytest

from squadron.pipeline.actions.judge import JudgeThresholds
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
