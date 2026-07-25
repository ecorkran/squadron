"""Tests for direction classification and current-threshold read (T7/T8)."""

from __future__ import annotations

import logging
from collections.abc import Generator

import pytest

from squadron.metrology.calibration import classify_direction, read_current_thresholds
from squadron.metrology.calibration_models import RecommendationDirection
from squadron.review.templates import ReviewTemplate, clear_registry, register_template

_FLOOR = 5
_GRADUATE_RATE = 0.9
_TIGHTEN_RATE = 0.6


def _classify(match_rate: float, n: int, *, versioned: bool = True) -> RecommendationDirection:
    return classify_direction(
        match_rate,
        n,
        _FLOOR,
        versioned=versioned,
        graduate_rate=_GRADUATE_RATE,
        tighten_rate=_TIGHTEN_RATE,
    )


class TestClassifyDirectionBands:
    @pytest.mark.parametrize(
        ("match_rate", "n", "expected"),
        [
            # Boundary: n exactly at floor, match_rate exactly at graduate_rate.
            (_GRADUATE_RATE, _FLOOR, RecommendationDirection.GRADUATE),
            # Above floor, above graduate rate.
            (0.95, 10, RecommendationDirection.GRADUATE),
            # Boundary: match_rate exactly at tighten_rate.
            (_TIGHTEN_RATE, 10, RecommendationDirection.TIGHTEN),
            # Below tighten rate.
            (0.3, 10, RecommendationDirection.TIGHTEN),
            # Mid-band: at/above floor, between tighten and graduate rates.
            (0.75, 10, RecommendationDirection.HOLD),
        ],
    )
    def test_direction_bands(
        self, match_rate: float, n: int, expected: RecommendationDirection
    ) -> None:
        assert _classify(match_rate, n) == expected

    def test_loosening_is_floor_gated(self) -> None:
        # n < floor with a high match rate must never return GRADUATE.
        result = _classify(0.99, n=_FLOOR - 1)
        assert result != RecommendationDirection.GRADUATE
        assert result == RecommendationDirection.INSUFFICIENT_EVIDENCE

    def test_tightening_is_not_floor_gated(self) -> None:
        # n < floor with a low match rate reaches TIGHTEN, not
        # INSUFFICIENT_EVIDENCE — the regression this task's design calls out.
        result = _classify(0.1, n=_FLOOR - 1)
        assert result == RecommendationDirection.TIGHTEN

    def test_unversioned_refusal_even_with_high_n_and_match_rate(self) -> None:
        result = _classify(0.99, n=1000, versioned=False)
        assert result == RecommendationDirection.INSUFFICIENT_EVIDENCE


class TestReadCurrentThresholds:
    @pytest.fixture(autouse=True)
    def _clear_registry(self) -> Generator[None]:  # pyright: ignore[reportUnusedFunction]
        clear_registry()
        yield
        clear_registry()

    def test_registered_template_returns_resolved_thresholds(self) -> None:
        register_template(
            ReviewTemplate(
                name="judge.example",
                description="Example",
                system_prompt="You are a judge.",
                allowed_tools=[],
                permission_mode="default",
                setting_sources=None,
                required_inputs=[],
                optional_inputs=[],
                prompt_template="Judge this: {input}",
                judge={"pass_floor": 78, "concerns_floor": 55},
            )
        )
        thresholds = read_current_thresholds("judge.example")
        assert thresholds is not None
        assert thresholds.pass_floor == 78.0
        assert thresholds.concerns_floor == 55.0

    def test_unregistered_template_returns_none_and_logs_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING, logger="squadron.metrology.calibration"):
            result = read_current_thresholds("no.such.template")
        assert result is None
        assert any(
            "no.such.template" in record.message and record.levelno == logging.WARNING
            for record in caplog.records
        )

    def test_malformed_judge_block_does_not_fabricate_a_threshold(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        # A non-numeric pass_floor: resolve_thresholds itself has no
        # fallback (bare float() raises) — read_current_thresholds catches
        # that and degrades to None + WARNING, never a raised exception and
        # never a fabricated threshold.
        register_template(
            ReviewTemplate(
                name="judge.malformed",
                description="Malformed",
                system_prompt="You are a judge.",
                allowed_tools=[],
                permission_mode="default",
                setting_sources=None,
                required_inputs=[],
                optional_inputs=[],
                prompt_template="Judge this: {input}",
                judge={"pass_floor": "not-a-number", "concerns_floor": 55},
            )
        )
        with caplog.at_level(logging.WARNING, logger="squadron.metrology.calibration"):
            result = read_current_thresholds("judge.malformed")
        assert result is None
        assert any(
            "judge.malformed" in record.message and record.levelno == logging.WARNING
            for record in caplog.records
        )
