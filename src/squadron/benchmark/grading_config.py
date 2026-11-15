"""Validators for the benchmark grading config keys (slice 425 D7, D8).

The validators take a raw config value, so a command that reads config through its own seam
applies the same rules wherever the value came from.
"""

from __future__ import annotations

from squadron.config.keys import (
    BENCHMARK_REVIEW_FLOOR_RUNS_KEY,
    BENCHMARK_REVIEW_TIMEOUT_KEY,
    BENCHMARK_TARGET_PASS_RATE_DIFFERENCE_KEY,
    REVIEW_FLOOR_RUNS_MINIMUM,
)


def check_review_floor_runs(value: object) -> int:
    """*value* as ``benchmark.review_floor_runs``; ``ValueError`` naming the key when invalid."""
    if isinstance(value, bool) or not isinstance(value, int) or value < REVIEW_FLOOR_RUNS_MINIMUM:
        raise ValueError(
            f"{BENCHMARK_REVIEW_FLOOR_RUNS_KEY} must be an integer of at least "
            f"{REVIEW_FLOOR_RUNS_MINIMUM}, got {value!r}"
        )
    return value


def check_review_timeout(value: object) -> float | None:
    """*value* as ``benchmark.review_timeout_s``: unset is ``None``, never a made-up number."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f"{BENCHMARK_REVIEW_TIMEOUT_KEY} must be a positive number, got {value!r}")
    return float(value)


def check_target_difference(value: object) -> float:
    """*value* as ``benchmark.target_pass_rate_difference``: a number strictly between 0 and 1."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value < 1:
        raise ValueError(
            f"{BENCHMARK_TARGET_PASS_RATE_DIFFERENCE_KEY} must be greater than 0 and less than 1, "
            f"got {value!r}"
        )
    return float(value)
