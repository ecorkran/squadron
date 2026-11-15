"""``review_floor``: the grading review's noise floor (slice 425 Task 22, D8)."""

from __future__ import annotations

import statistics

import pytest

from squadron.benchmark.grade_review import review_floor
from squadron.metrology.grade_models import ReviewOutcome
from squadron.review.models import Severity
from tests.benchmark.test_grade_identity import finding


def outcome(count: int) -> ReviewOutcome:
    return ReviewOutcome(
        findings=tuple(finding(Severity.CONCERN, index) for index in range(count)),
        unnormalized_count=0,
        cost_usd=0.1,
        rules_hash=None,
    )


def test_three_outcomes_give_min_max_mean_and_the_sample_stddev() -> None:
    floor = review_floor([outcome(2), outcome(4), outcome(3)], runs=3)
    assert (floor.min, floor.max, floor.mean) == (2, 4, 3.0)
    assert floor.stddev == pytest.approx(statistics.stdev([2, 4, 3]))
    assert floor.stddev == pytest.approx(1.0)


def test_two_outcomes_work() -> None:
    floor = review_floor([outcome(1), outcome(5)], runs=2)
    assert (floor.min, floor.max, floor.mean) == (1, 5, 3.0)


def test_one_outcome_raises() -> None:
    with pytest.raises(ValueError, match="at least 2"):
        review_floor([outcome(2)], runs=1)


def test_fewer_outcomes_than_runs_raises() -> None:
    with pytest.raises(ValueError, match="only 2 outcomes"):
        review_floor([outcome(2), outcome(3)], runs=3)


def test_runs_below_two_raises_even_with_outcomes() -> None:
    with pytest.raises(ValueError, match="at least 2"):
        review_floor([outcome(2), outcome(3)], runs=1)
