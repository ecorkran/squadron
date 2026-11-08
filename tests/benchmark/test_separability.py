"""Minimum detectable difference and required cases, against hand-computed values (D12)."""

from __future__ import annotations

import pytest

from squadron.benchmark.separability import (
    ASSUMPTION,
    POWER,
    SIGNIFICANCE,
    assess,
    cases_needed,
    minimum_detectable_difference,
)


def test_the_significance_and_power_constants() -> None:
    assert (SIGNIFICANCE, POWER) == (0.05, 0.80)


def test_three_samples_and_a_target_of_a_fifth_need_33_cases() -> None:
    assert cases_needed(0.20, 3) == 33


def test_33_cases_are_enough_and_32_are_not() -> None:
    enough = minimum_detectable_difference(33, 3)
    short = minimum_detectable_difference(32, 3)
    assert enough == pytest.approx(0.1991, abs=5e-4)
    assert short == pytest.approx(0.2022, abs=5e-4)
    assert assess(33, 3, 0.20).enough is True
    assert assess(32, 3, 0.20).enough is False


@pytest.mark.parametrize(
    ("target", "samples", "expected"),
    [(0.10, 1, 393), (0.10, 3, 131), (0.25, 5, 13), (0.50, 3, 6)],
)
def test_other_hand_computed_case_counts(target: float, samples: int, expected: int) -> None:
    # ceil((1.95996 + 0.84162)^2 * 0.5 / samples / target^2)
    assert cases_needed(target, samples) == expected


def test_the_bound_shrinks_with_cases_and_samples() -> None:
    assert minimum_detectable_difference(10, 3) == pytest.approx(0.3617, abs=5e-4)
    one = minimum_detectable_difference(10, 1)
    four = minimum_detectable_difference(10, 4)
    assert one is not None and four is not None
    assert one == pytest.approx(2 * four)


def test_no_qualified_cases_is_an_explicit_result_not_a_division_error() -> None:
    assert minimum_detectable_difference(0, 3) is None
    assessment = assess(0, 3, 0.20)
    assert assessment.no_qualified_cases is True
    assert assessment.enough is False
    assert assessment.minimum_difference is None
    assert assessment.cases_needed == 33


@pytest.mark.parametrize(
    "call",
    [
        lambda: minimum_detectable_difference(5, 0),
        lambda: minimum_detectable_difference(-1, 3),
        lambda: cases_needed(0.2, 0),
        lambda: cases_needed(0.0, 3),
        lambda: cases_needed(1.0, 3),
        lambda: cases_needed(-0.1, 3),
        lambda: assess(5, 3, 1.5),
    ],
    ids=[
        "zero samples",
        "negative cases",
        "zero samples needed",
        "zero target",
        "target one",
        "negative target",
        "assess",
    ],
)
def test_invalid_inputs_raise(call: object) -> None:
    with pytest.raises(ValueError):
        call()  # type: ignore[operator]


def test_the_assumption_sentence_names_what_the_bound_assumes() -> None:
    assert "independent" in ASSUMPTION and "425" in ASSUMPTION
