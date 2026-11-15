"""``ReviewBudget``: the shared grading cap (slice 425 Task 23, D9)."""

from __future__ import annotations

import logging

import pytest

from squadron.benchmark.grade_budget import GradeCapReached, ReviewBudget


def test_under_the_cap_passes() -> None:
    budget = ReviewBudget(cap_usd=1.0, per_review_usd=0.2)
    budget.after_review(0.4)
    budget.before_review()
    assert budget.spent == pytest.approx(0.4)


def test_at_the_cap_raises_and_logs_a_warning(caplog: pytest.LogCaptureFixture) -> None:
    budget = ReviewBudget(cap_usd=1.0, per_review_usd=0.2)
    budget.after_review(1.0)
    with caplog.at_level(logging.WARNING), pytest.raises(GradeCapReached) as reached:
        budget.before_review()
    assert reached.value.spent_usd == pytest.approx(1.0)
    assert reached.value.cap_usd == 1.0
    assert any(r.levelno == logging.WARNING for r in caplog.records)


def test_a_review_that_crosses_the_cap_is_allowed_and_the_next_is_refused() -> None:
    budget = ReviewBudget(cap_usd=1.0, per_review_usd=0.2)
    budget.after_review(0.9)
    budget.before_review()  # the check is before the review, so this one runs
    budget.after_review(0.5)  # ... and crosses the cap
    with pytest.raises(GradeCapReached):
        budget.before_review()


def test_an_unreported_cost_counts_at_the_per_review_figure_and_is_tallied() -> None:
    budget = ReviewBudget(cap_usd=10.0, per_review_usd=0.25)
    budget.after_review(None)
    budget.after_review(None)
    assert budget.spent == pytest.approx(0.5)
    assert budget.unpriced == 2


def test_spent_sums_priced_and_unpriced_alike() -> None:
    budget = ReviewBudget(cap_usd=10.0, per_review_usd=0.25)
    budget.after_review(0.1)
    budget.after_review(None)
    budget.after_review(0.3)
    assert budget.spent == pytest.approx(0.65)
    assert budget.unpriced == 1


@pytest.mark.parametrize(("cap", "per_review"), [(0, 0.1), (-1, 0.1), (1.0, 0), (1.0, -0.1)])
def test_a_non_positive_figure_is_refused(cap: float, per_review: float) -> None:
    with pytest.raises(ValueError, match="positive"):
        ReviewBudget(cap_usd=cap, per_review_usd=per_review)
