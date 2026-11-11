"""How many qualified cases are enough to separate two configs (slice 422 D12).

An analytic bound until 425 measures real variance. With ``n`` qualified cases and ``k``
samples per case, each config's per-case value is a pass fraction. The bound takes the worst
case per-case variance for independent outcomes, p = 0.5 for both configs, which gives
Var(D) <= 0.5 / k for the difference D. Then, with z the standard normal quantiles for the
two-sided significance level and the power:

    MDD = (z_{1-alpha/2} + z_power) * sqrt(0.5 / k) / sqrt(n)
    n   = ceil((z_{1-alpha/2} + z_power)^2 * 0.5 / k / d^2)

It assumes outcomes within a case are independent and the true difference is the same in every
case; ``ASSUMPTION`` says so wherever the answer is shown.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import NormalDist

SIGNIFICANCE = 0.05
POWER = 0.80
#: The worst-case per-case variance of a pass fraction over ``k`` samples is this over ``k``.
WORST_CASE_VARIANCE = 0.5

ASSUMPTION = (
    "assumes independent outcomes, p=0.5, constant per-case difference; "
    '"enough" fails if per-case differences vary; 425 replaces this with measured variance'
)


def _z_total() -> float:
    standard = NormalDist()
    return standard.inv_cdf(1 - SIGNIFICANCE / 2) + standard.inv_cdf(POWER)


def _check_samples(samples_per_case: int) -> None:
    if samples_per_case < 1:
        raise ValueError(f"samples per case must be at least 1, got {samples_per_case}")


def _check_target(target_difference: float) -> None:
    if not 0 < target_difference < 1:
        raise ValueError(f"target difference must be between 0 and 1, got {target_difference}")


def minimum_detectable_difference(qualified_cases: int, samples_per_case: int) -> float | None:
    """The smallest pass-rate difference ``n`` cases can detect, ``None`` when there are no cases."""
    _check_samples(samples_per_case)
    if qualified_cases < 0:
        raise ValueError(f"qualified cases cannot be negative, got {qualified_cases}")
    if qualified_cases == 0:
        return None
    return _z_total() * math.sqrt(WORST_CASE_VARIANCE / samples_per_case) / math.sqrt(qualified_cases)


def cases_needed(target_difference: float, samples_per_case: int) -> int:
    """The qualified cases needed to detect ``target_difference``."""
    _check_samples(samples_per_case)
    _check_target(target_difference)
    needed = _z_total() ** 2 * WORST_CASE_VARIANCE / samples_per_case / target_difference**2
    return math.ceil(needed)


@dataclass(frozen=True)
class SeparabilityAssessment:
    """The answer for one project or pool: whether its qualified cases can separate two configs."""

    qualified_cases: int
    samples_per_case: int
    target_difference: float
    minimum_difference: float | None
    cases_needed: int

    @property
    def no_qualified_cases(self) -> bool:
        return self.qualified_cases == 0

    @property
    def enough(self) -> bool:
        return self.minimum_difference is not None and self.minimum_difference <= self.target_difference


def assess(
    qualified_cases: int, samples_per_case: int, target_difference: float
) -> SeparabilityAssessment:
    """Combine the two bounds for ``qualified_cases`` against the target difference."""
    return SeparabilityAssessment(
        qualified_cases=qualified_cases,
        samples_per_case=samples_per_case,
        target_difference=target_difference,
        minimum_difference=minimum_detectable_difference(qualified_cases, samples_per_case),
        cases_needed=cases_needed(target_difference, samples_per_case),
    )
