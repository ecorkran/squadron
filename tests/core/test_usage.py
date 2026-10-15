"""Tests for the provider-neutral usage types (slice 931 D8)."""

from __future__ import annotations

import pytest

from squadron.core.usage import (
    CostBasis,
    RunTelemetry,
    TokenUsage,
    UsageRecord,
    add_optional,
    add_optional_float,
)


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


# --- slice 175 -------------------------------------------------------------------------


def test_cache_write_sums_and_stays_none_when_unreported() -> None:
    assert TokenUsage(cache_write=3).plus(TokenUsage(cache_write=4)).cache_write == 7
    assert TokenUsage(cache_write=3).plus(TokenUsage()).cache_write == 3
    assert TokenUsage(prompt=1).plus(TokenUsage(prompt=2)).cache_write is None


def test_reported_true_when_only_cache_write_set() -> None:
    assert TokenUsage(cache_write=0).reported


@pytest.mark.parametrize(
    ("total", "value", "expected"),
    [(None, None, None), (None, 0.5, 0.5), (0.25, 0.5, 0.75), (0.25, None, 0.25)],
)
def test_add_optional_float(total: float | None, value: float | None, expected: float | None) -> None:
    assert add_optional_float(total, value) == expected


def test_fold_result_sums_turns_tokens_and_cost() -> None:
    telemetry = RunTelemetry()

    telemetry.fold_result(turns=3, usage=TokenUsage(prompt=10, cache_write=2), cost_usd=0.25)
    telemetry.fold_result(turns=2, usage=TokenUsage(prompt=5, cached=4), cost_usd=0.5)

    assert telemetry.turns == 5
    assert telemetry.usage == TokenUsage(prompt=15, cached=4, cache_write=2)
    assert telemetry.cost_usd == 0.75


def test_fold_result_keeps_none_cost_when_never_reported() -> None:
    telemetry = RunTelemetry()

    telemetry.fold_result(turns=1, usage=None, cost_usd=None)
    telemetry.fold_result(turns=None, usage=None, cost_usd=None)

    assert telemetry.turns == 1
    assert telemetry.cost_usd is None
    assert not telemetry.usage.reported


def _full_record(*, partial: bool = False) -> UsageRecord:
    return UsageRecord(
        model="claude-opus",
        alias="opus",
        profile="sdk",
        effort="high",
        turns=12,
        duration_seconds=84.2,
        usage=TokenUsage(prompt=412803, cached=380112, cache_write=21011, completion=9214),
        cost_usd=0.41,
        cost_basis=CostBasis.PROVIDER,
        partial=partial,
    )


def test_record_to_dict_persisted_shape() -> None:
    assert _full_record().to_dict() == {
        "model": "claude-opus",
        "alias": "opus",
        "profile": "sdk",
        "effort": "high",
        "turns": 12,
        "duration_seconds": 84.2,
        "tokens": {
            "prompt": 412803,
            "cached": 380112,
            "cache_write": 21011,
            "completion": 9214,
            "reasoning": None,
        },
        "cost_usd": 0.41,
        "cost_basis": "provider",
    }


@pytest.mark.parametrize(
    "record",
    [
        _full_record(),
        _full_record(partial=True),
        UsageRecord(
            model=None,
            alias=None,
            profile=None,
            effort=None,
            turns=None,
            duration_seconds=None,
            usage=TokenUsage(),
            cost_usd=None,
            cost_basis=None,
        ),
    ],
)
def test_record_round_trip(record: UsageRecord) -> None:
    assert UsageRecord.from_dict(record.to_dict()) == record


def test_partial_key_present_only_when_true() -> None:
    assert _full_record(partial=True).to_dict()["partial"] is True
    assert "partial" not in _full_record().to_dict()


def test_from_dict_missing_optional_keys_read_as_none() -> None:
    record = UsageRecord.from_dict({"turns": 2})

    assert record.turns == 2
    assert record.model is None
    assert record.usage == TokenUsage()
    assert record.cost_basis is None


@pytest.mark.parametrize(
    ("raw", "key"),
    [
        ({"tokens": [1, 2]}, "tokens"),
        ({"turns": "3"}, "turns"),
        ({"cost_basis": "guess"}, "cost_basis"),
        ({"tokens": {"prompt": True}}, "prompt"),
    ],
)
def test_from_dict_rejects_malformed_fields(raw: dict[str, object], key: str) -> None:
    with pytest.raises(ValueError, match=key):
        UsageRecord.from_dict(raw)
