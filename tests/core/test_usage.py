"""Tests for the provider-neutral usage types (slice 931 D8)."""

from __future__ import annotations

import pytest

from squadron.core.usage import RunTelemetry, TokenUsage, add_optional


@pytest.mark.parametrize(
    ("total", "value", "expected"),
    [(None, None, None), (None, 4, 4), (4, None, 4), (4, 5, 9), (0, None, 0), (None, 0, 0)],
)
def test_add_optional(total: int | None, value: int | None, expected: int | None) -> None:
    assert add_optional(total, value) == expected


def test_token_usage_sum_keeps_none_only_when_both_sides_none() -> None:
    left = TokenUsage(prompt=10, cached=None, completion=None, reasoning=None)
    right = TokenUsage(prompt=5, cached=3, completion=None, reasoning=None)

    total = left.plus(right)

    assert total == TokenUsage(prompt=15, cached=3, completion=None, reasoning=None)


def test_token_usage_reported() -> None:
    assert not TokenUsage().reported
    assert TokenUsage(cached=0).reported


def test_run_telemetry_folds_turns_reasoning_and_usage() -> None:
    telemetry = RunTelemetry()

    telemetry.fold_turn(reasoning_chars=100, usage=TokenUsage(prompt=10, completion=2))
    telemetry.fold_turn(reasoning_chars=50, usage=None)
    telemetry.fold_turn(reasoning_chars=0, usage=TokenUsage(prompt=20, reasoning=7))

    assert telemetry.turns == 3
    assert telemetry.reasoning_chars == 150
    assert telemetry.usage == TokenUsage(prompt=30, cached=None, completion=2, reasoning=7)


def test_snapshot_is_independent_of_later_folds() -> None:
    telemetry = RunTelemetry()
    telemetry.fold_turn(reasoning_chars=5, usage=TokenUsage(prompt=1))

    snapshot = telemetry.snapshot()
    telemetry.fold_turn(reasoning_chars=5, usage=TokenUsage(prompt=1))

    assert snapshot.turns == 1
    assert snapshot.reasoning_chars == 5
    assert snapshot.usage == TokenUsage(prompt=1)
