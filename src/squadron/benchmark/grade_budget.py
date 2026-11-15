"""The run-level cap on grading spend (slice 425 D9).

One ``ReviewBudget`` is shared by every ``grade_one`` call in a grade invocation. The cap is
checked before each review, so the last review may cross it by one review's cost, which is
the overshoot the printed bound states. A review with no reported cost counts at the
per-review figure and is tallied, so the summary can say how many were estimated.
"""

from __future__ import annotations

import logging

_logger = logging.getLogger(__name__)


class GradeCapReached(Exception):
    """Spend reached the run cap; grading stops and keeps every record already written."""

    def __init__(self, spent_usd: float, cap_usd: float) -> None:
        super().__init__(f"grading spend ${spent_usd:.2f} reached the run cap ${cap_usd:.2f}")
        self.spent_usd = spent_usd
        self.cap_usd = cap_usd


class ReviewBudget:
    def __init__(self, cap_usd: float, per_review_usd: float) -> None:
        if cap_usd <= 0:
            raise ValueError(f"the run cap must be positive, got {cap_usd!r}")
        if per_review_usd <= 0:
            raise ValueError(f"the per-review figure must be positive, got {per_review_usd!r}")
        self._cap_usd = cap_usd
        self._per_review_usd = per_review_usd
        self._spent_usd = 0.0
        self._unpriced = 0

    @property
    def spent(self) -> float:
        """Priced and unpriced reviews alike, the latter at the per-review figure."""
        return self._spent_usd

    @property
    def unpriced(self) -> int:
        """How many reviews reported no cost and were counted at the per-review figure."""
        return self._unpriced

    def before_review(self) -> None:
        """Raise ``GradeCapReached`` when spend is at or above the cap; call before every review."""
        if self._spent_usd >= self._cap_usd:
            _logger.warning(
                "grading run cap reached: spent $%.2f of $%.2f", self._spent_usd, self._cap_usd
            )
            raise GradeCapReached(self._spent_usd, self._cap_usd)

    def after_review(self, cost_usd: float | None) -> None:
        """Add a review's cost, or the per-review figure when it reported none."""
        if cost_usd is None:
            self._unpriced += 1
            self._spent_usd += self._per_review_usd
        else:
            self._spent_usd += cost_usd
