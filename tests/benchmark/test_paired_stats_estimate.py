"""``estimate_sample_count`` against hand-computed values (slice 425 Task 33, D15)."""

from __future__ import annotations

import math

import pytest

from squadron.benchmark.paired_stats import (
    MIN_PAIRED_CASES,
    PROJECTED_SAMPLE_COUNTS,
    PerCaseSamples,
    estimate_sample_count,
)
from squadron.benchmark.separability import POWER, SIGNIFICANCE

#: z(0.975) + z(0.80) for SIGNIFICANCE 0.05 and POWER 0.80, to the digits used below.
Z = 2.8015852
T, F = True, False
TARGET = 0.2


def pair(a: dict[str, list[bool]], b: dict[str, list[bool]]) -> PerCaseSamples:
    return {"a": a, "b": b}


#: Within-case noise but no between-case spread: k = 2, n = 5.
NOISY = pair(
    {"c1": [T, T], "c2": [T, F], "c3": [F, F], "c4": [T, T], "c5": [T, F]},
    {"c1": [T, F], "c2": [F, F], "c3": [F, F], "c4": [T, F], "c5": [F, F]},
)
#: Each case answers the same way every sample: sigma_w = 0, differences [0, 1, 0, 0, 1].
CONSISTENT = pair(
    {"c1": [T, T], "c2": [T, T], "c3": [F, F], "c4": [F, F], "c5": [T, T]},
    {"c1": [T, T], "c2": [F, F], "c3": [F, F], "c4": [F, F], "c5": [F, F]},
)


def needed(estimate_cases: tuple[object, ...]) -> dict[int, int]:
    return {item.samples: item.cases for item in estimate_cases}  # type: ignore[attr-defined]


def test_the_constants_are_the_422_ones() -> None:
    assert (SIGNIFICANCE, POWER) == (0.05, 0.80)
    assert PROJECTED_SAMPLE_COUNTS == (1, 2, 3, 5)


def test_a_noisy_fixture_has_hand_computed_variances_and_mdd() -> None:
    (estimate,) = estimate_sample_count(NOISY, TARGET)
    # Each mixed case has sample variance 0.5; A has two of five, B two of five: 0.2 + 0.2.
    assert estimate.within_case_variance == pytest.approx(0.4)
    # d = [.5, .5, 0, .5, .5]: variance 0.05, and 0.05 - 0.4 / 2 < 0, so it floors at zero.
    assert estimate.between_case_variance == 0.0
    # MDD(n=5, k=2) = Z * sqrt((0 + 0.4 / 2) / 5) = Z * 0.2
    assert estimate.mdd_now == pytest.approx(Z * 0.2, abs=1e-6)
    assert (estimate.config_a, estimate.config_b) == ("a", "b")


def test_cases_needed_by_hand_for_k_1_and_k_3() -> None:
    (estimate,) = estimate_sample_count(NOISY, TARGET)
    by_k = needed(estimate.cases_needed)
    # ceil(Z^2 * (0 + 0.4 / k) / 0.2^2) = ceil(78.4888 / k)
    assert by_k[1] == 79
    assert by_k[3] == 27
    assert by_k == {1: 79, 2: 40, 3: 27, 5: 16}


def test_between_case_variance_is_the_excess_over_within_noise() -> None:
    (estimate,) = estimate_sample_count(CONSISTENT, TARGET)
    assert estimate.within_case_variance == 0.0
    # d = [0, 1, 0, 0, 1], mean 0.4, sample variance 1.2 / 4 = 0.3
    assert estimate.between_case_variance == pytest.approx(0.3)
    assert estimate.mdd_now == pytest.approx(Z * math.sqrt(0.3 / 5), abs=1e-6)
    # ceil(Z^2 * 0.3 / 0.04) = ceil(58.87), the same at every k because sigma_w = 0
    assert needed(estimate.cases_needed) == {1: 59, 2: 59, 3: 59, 5: 59}


def test_zero_variance_gives_mdd_zero_and_the_minimum_case_count() -> None:
    same = {f"c{i}": [T, T] for i in range(6)}
    (estimate,) = estimate_sample_count(pair(same, dict(same)), TARGET)
    assert estimate.within_case_variance == 0.0
    assert estimate.between_case_variance == 0.0
    assert estimate.mdd_now == 0.0
    assert set(needed(estimate.cases_needed).values()) == {MIN_PAIRED_CASES}


def test_k_of_one_returns_nothing() -> None:
    one_sample = {f"c{i}": [T] for i in range(6)}
    assert estimate_sample_count(pair(one_sample, dict(one_sample)), TARGET) == ()


def test_four_cases_return_nothing() -> None:
    four = {f"c{i}": [T, F] for i in range(MIN_PAIRED_CASES - 1)}
    assert estimate_sample_count(pair(four, dict(four)), TARGET) == ()


def test_one_config_returns_nothing() -> None:
    assert estimate_sample_count({"a": NOISY["a"]}, TARGET) == ()


def test_only_cases_both_configs_have_count() -> None:
    a = {**NOISY["a"], "extra": [T, T]}
    (estimate,) = estimate_sample_count(pair(a, NOISY["b"]), TARGET)
    assert estimate.within_case_variance == pytest.approx(0.4)


def test_three_configs_give_three_sorted_pairs() -> None:
    samples: PerCaseSamples = {"c": NOISY["a"], "a": NOISY["a"], "b": NOISY["b"]}
    pairs = [(e.config_a, e.config_b) for e in estimate_sample_count(samples, TARGET)]
    assert pairs == [("a", "b"), ("a", "c"), ("b", "c")]


def test_differing_sample_counts_are_refused() -> None:
    a = dict(NOISY["a"])
    a["c1"] = [T, T, T]
    with pytest.raises(ValueError, match="differing sample counts"):
        estimate_sample_count(pair(a, NOISY["b"]), TARGET)


@pytest.mark.parametrize("target", [0.0, 1.0, -0.1, 1.5])
def test_a_target_outside_zero_one_is_refused(target: float) -> None:
    with pytest.raises(ValueError, match="between 0 and 1"):
        estimate_sample_count(NOISY, target)


def test_the_function_is_deterministic() -> None:
    assert estimate_sample_count(NOISY, TARGET) == estimate_sample_count(NOISY, TARGET)
