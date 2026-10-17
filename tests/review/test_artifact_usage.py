"""Cumulative artifact usage: fold, frontmatter fields, and the malformed-prior rule (178 D2)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from squadron.core.usage import CostBasis, TokenUsage, UsageRecord
from squadron.review.artifact_usage import (
    PRICED_ROUNDS_KEY,
    USAGE_ROUNDS_KEY,
    ArtifactUsage,
    artifact_usage_fields,
    fold,
    read_artifact_usage,
)

_PATH = Path("project-documents/user/slices/178-slice.example.md")


def _record(
    cost_usd: float | None = 0.5,
    turns: int | None = 2,
    usage: TokenUsage | None = None,
    duration: float | None = 4.0,
) -> UsageRecord:
    return UsageRecord(
        model="m",
        alias=None,
        profile=None,
        effort=None,
        turns=turns,
        duration_seconds=duration,
        usage=usage or TokenUsage(prompt=100, completion=10),
        cost_usd=cost_usd,
        cost_basis=CostBasis.PROVIDER if cost_usd is not None else None,
    )


def test_fold_from_none_equals_the_record() -> None:
    usage = fold(None, _record())
    assert usage.rounds == 1
    assert usage.priced_rounds == 1
    assert usage.cost.turns == 2
    assert usage.cost.usage == TokenUsage(prompt=100, completion=10)
    assert usage.cost.duration_seconds == 4.0
    assert usage.cost.cost_usd == 0.5


def test_unpriced_round_counts_but_adds_no_cost() -> None:
    first = fold(None, _record(cost_usd=0.5))
    second = fold(first, _record(cost_usd=None))
    third = fold(second, _record(cost_usd=0.25))
    assert second.cost.cost_usd == 0.5
    assert second.priced_rounds == 1
    assert third.cost.cost_usd == pytest.approx(0.75)
    assert (third.rounds, third.priced_rounds) == (3, 2)
    assert third.cost.turns == 6


def test_fold_of_only_unpriced_rounds_keeps_cost_unreported() -> None:
    usage = fold(fold(None, _record(cost_usd=None)), _record(cost_usd=None))
    assert usage.cost.cost_usd is None
    assert "costUsd" not in artifact_usage_fields(usage)


def test_token_field_nobody_reported_is_absent() -> None:
    record = _record(usage=TokenUsage(prompt=7))
    fields = artifact_usage_fields(fold(fold(None, record), record))
    assert fields["promptTokens"] == 14
    assert "cachedTokens" not in fields
    assert "reasoningTokens" not in fields


def test_token_field_reported_by_one_round_equals_that_value() -> None:
    first = fold(None, _record(usage=TokenUsage(prompt=7)))
    second = fold(first, _record(usage=TokenUsage(prompt=1, cached=3)))
    assert artifact_usage_fields(second)["cachedTokens"] == 3


def test_fields_never_contain_cost_basis() -> None:
    fields = artifact_usage_fields(fold(None, _record()))
    assert "costBasis" not in fields
    assert fields[USAGE_ROUNDS_KEY] == 1
    assert fields[PRICED_ROUNDS_KEY] == 1


def test_read_round_trips_fields() -> None:
    usage = fold(fold(None, _record()), _record(cost_usd=None))
    read = read_artifact_usage(_PATH, artifact_usage_fields(usage))
    assert read is not None
    assert (read.rounds, read.priced_rounds) == (2, 1)
    assert read.cost.turns == usage.cost.turns
    assert read.cost.usage == usage.cost.usage
    assert read.cost.cost_usd == usage.cost.cost_usd
    assert read.cost.duration_seconds == usage.cost.duration_seconds


def test_missing_usage_rounds_is_none_without_warning(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        assert read_artifact_usage(_PATH, {"status": "complete", "costUsd": 1.0}) is None
    assert caplog.records == []


_GOOD: dict[str, object] = {USAGE_ROUNDS_KEY: 2, PRICED_ROUNDS_KEY: 1, "costUsd": 0.5, "turns": 3}


@pytest.mark.parametrize(
    ("key", "value"),
    [
        (USAGE_ROUNDS_KEY, 0),
        (USAGE_ROUNDS_KEY, "two"),
        (USAGE_ROUNDS_KEY, True),
        (PRICED_ROUNDS_KEY, -1),
        (PRICED_ROUNDS_KEY, 1.5),
        ("costUsd", "free"),
        ("durationSeconds", "long"),
        ("turns", 2.5),
        ("promptTokens", "many"),
    ],
)
def test_malformed_prior_returns_none_and_names_path_and_key(
    key: str, value: object, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        assert read_artifact_usage(_PATH, {**_GOOD, key: value}) is None
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert str(_PATH) in warnings[0]
    assert key in warnings[0]


def test_missing_priced_rounds_is_malformed(caplog: pytest.LogCaptureFixture) -> None:
    front = {USAGE_ROUNDS_KEY: 1, "costUsd": 0.5}
    with caplog.at_level(logging.WARNING):
        assert read_artifact_usage(_PATH, front) is None
    assert PRICED_ROUNDS_KEY in caplog.text


def test_artifact_usage_is_frozen() -> None:
    usage = fold(None, _record())
    assert isinstance(usage, ArtifactUsage)
    with pytest.raises(AttributeError):
        usage.rounds = 5  # type: ignore[misc]
