"""Paired per-case reduction and bootstrap against hand-computed values (slice 425 Task 32)."""

from __future__ import annotations

import subprocess
import sys

import pytest

from squadron.benchmark.paired_stats import (
    BOOTSTRAP_RESAMPLES,
    MIN_PAIRED_CASES,
    bootstrap_mean_interval,
    case_pass_fraction,
    compare_pair,
    pair_seed,
    paired_differences,
)
from squadron.metrology.grade_models import PairVerdict

SEED = 7


def test_the_pass_fraction_of_two_passes_in_three_samples_is_two_thirds() -> None:
    assert case_pass_fraction([True, True, False]) == pytest.approx(2 / 3)


def test_a_config_absence_passed_as_false_counts_as_a_fail() -> None:
    assert case_pass_fraction([True, False, False]) == pytest.approx(1 / 3)


def test_a_case_with_no_samples_is_refused() -> None:
    with pytest.raises(ValueError, match="at least one sample"):
        case_pass_fraction([])


def test_paired_differences_are_in_case_id_order() -> None:
    a = {"case-b": 1.0, "case-a": 0.5, "case-c": 0.0}
    b = {"case-a": 0.0, "case-b": 0.25, "case-c": 0.0}
    assert paired_differences(a, b) == [0.5, 0.75, 0.0]


def test_paired_differences_refuse_different_case_sets() -> None:
    with pytest.raises(ValueError, match="case-z"):
        paired_differences({"case-a": 1.0, "case-z": 0.0}, {"case-a": 1.0})


def test_a_constant_difference_has_a_degenerate_interval_and_leads() -> None:
    result = compare_pair([0.2] * 6, SEED)
    assert result.mean == pytest.approx(0.2)
    assert result.low == pytest.approx(0.2)
    assert result.high == pytest.approx(0.2)
    assert result.verdict is PairVerdict.A_AHEAD
    assert result.n == 6


def test_a_constant_negative_difference_means_b_leads() -> None:
    assert compare_pair([-0.2] * 6, SEED).verdict is PairVerdict.B_AHEAD


def test_a_symmetric_pair_has_an_interval_containing_zero() -> None:
    result = compare_pair([0.2, -0.2, 0.2, -0.2, 0.2, -0.2], SEED)
    assert result.mean == pytest.approx(0.0)
    assert result.low is not None and result.high is not None
    assert result.low <= 0 <= result.high
    assert result.verdict is PairVerdict.NOT_DISTINGUISHABLE


def test_a_pair_with_no_difference_at_all_is_not_distinguishable() -> None:
    assert compare_pair([0.0] * 6, SEED).verdict is PairVerdict.NOT_DISTINGUISHABLE


def test_fewer_cases_than_the_minimum_gives_too_few_cases_and_no_interval() -> None:
    result = compare_pair([0.2] * (MIN_PAIRED_CASES - 1), SEED)
    assert result.verdict is PairVerdict.TOO_FEW_CASES
    assert (result.low, result.high) == (None, None)
    assert result.mean == pytest.approx(0.2)


def test_the_same_seed_gives_the_same_interval_and_a_different_seed_may_differ() -> None:
    values = [0.0, 0.17, -0.31, 0.52, 0.08, -0.44, 0.29, 0.61, -0.12, 0.37]
    assert bootstrap_mean_interval(values, 1) == bootstrap_mean_interval(values, 1)
    assert bootstrap_mean_interval(values, 1) != bootstrap_mean_interval(values, 2)


def test_the_interval_brackets_the_sample_mean_of_varied_data() -> None:
    values = [0.0, 1.0, 0.5, -0.5, 1.0, 0.0, 0.5, -1.0]
    low, high = bootstrap_mean_interval(values, 3)
    assert low < sum(values) / len(values) < high


def test_an_empty_interval_input_is_refused() -> None:
    with pytest.raises(ValueError, match="at least one value"):
        bootstrap_mean_interval([], 1)


def test_the_resample_count_is_the_design_constant() -> None:
    assert BOOTSTRAP_RESAMPLES == 10_000
    assert MIN_PAIRED_CASES == 5


def test_pair_seed_is_one_value_for_both_orders_and_depends_on_the_benchmark() -> None:
    assert pair_seed("bench-1", "opus", "sol") == pair_seed("bench-1", "sol", "opus")
    assert pair_seed("bench-1", "opus", "sol") != pair_seed("bench-2", "opus", "sol")
    assert pair_seed("bench-1", "opus", "sol") != pair_seed("bench-1", "opus", "luna")


def test_the_seed_and_interval_do_not_depend_on_the_process_hash_seed() -> None:
    program = (
        "from squadron.benchmark.paired_stats import pair_seed, bootstrap_mean_interval\n"
        "s = pair_seed('bench-1', 'opus', 'sol')\n"
        "print(s, bootstrap_mean_interval([0.0, 1.0, 0.5, -0.5, 1.0, 0.0], s))\n"
    )
    outputs = []
    for hash_seed in ("1", "2"):
        done = subprocess.run(
            [sys.executable, "-c", program],
            capture_output=True,
            text=True,
            check=True,
            env={"PYTHONHASHSEED": hash_seed, "PATH": "/usr/bin:/bin"},
        )
        outputs.append(done.stdout)
    assert outputs[0] == outputs[1]
    assert outputs[0].strip()
