"""Per-model split of an artifact's stamped cost (#267)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from squadron.core.usage import CostBasis, TokenUsage, UsageRecord
from squadron.review.artifact_usage import (
    USAGE_ROUNDS_KEY,
    artifact_usage_fields,
    fold,
    read_artifact_usage,
)
from squadron.review.model_share import UNKNOWN_MODEL, USAGE_BY_MODEL_KEY, ModelShare

_PATH = Path("project-documents/user/tasks/266-tasks.example.md")


def _record(model: str | None, cost_usd: float | None = 0.5) -> UsageRecord:
    return UsageRecord(
        model=model,
        alias=None,
        profile=None,
        effort=None,
        turns=1,
        duration_seconds=1.0,
        usage=TokenUsage(prompt=100, completion=10),
        cost_usd=cost_usd,
        cost_basis=CostBasis.PROVIDER if cost_usd is not None else None,
    )


def test_one_model_creates_and_another_revises() -> None:
    usage = fold(fold(fold(None, _record("opus", 0.6)), _record("sonnet", 0.2)), _record("sonnet", 0.1))

    assert usage.by_model == {
        "opus": ModelShare(rounds=1, cost_usd=0.6, completion_tokens=10),
        "sonnet": ModelShare(rounds=2, cost_usd=pytest.approx(0.3), completion_tokens=20),
    }
    assert usage.cost.cost_usd == pytest.approx(0.9)


def test_a_round_with_no_model_is_counted_as_unknown() -> None:
    usage = fold(None, _record(None))
    assert usage.by_model[UNKNOWN_MODEL].rounds == 1


def test_an_unpriced_share_writes_no_cost() -> None:
    fields = artifact_usage_fields(fold(None, _record("m", cost_usd=None)))
    assert fields[USAGE_BY_MODEL_KEY] == {"m": {"rounds": 1, "completionTokens": 10}}


def test_split_round_trips_through_frontmatter() -> None:
    usage = fold(fold(None, _record("opus", 0.6)), _record("sonnet", None))
    read = read_artifact_usage(_PATH, artifact_usage_fields(usage))
    assert read is not None
    assert read.by_model == usage.by_model


def test_an_artifact_stamped_before_the_split_folds_on_without_backfill() -> None:
    old = artifact_usage_fields(fold(fold(None, _record("x")), _record("x")))
    del old[USAGE_BY_MODEL_KEY]
    prior = read_artifact_usage(_PATH, old)

    usage = fold(prior, _record("sonnet"))

    assert usage.rounds == 3
    assert usage.by_model == {"sonnet": ModelShare(rounds=1, cost_usd=0.5, completion_tokens=10)}


def test_malformed_split_warns_and_keeps_the_totals(caplog: pytest.LogCaptureFixture) -> None:
    fields = artifact_usage_fields(fold(None, _record("m")))
    fields[USAGE_BY_MODEL_KEY] = {"m": {"rounds": "one"}}

    with caplog.at_level(logging.WARNING):
        read = read_artifact_usage(_PATH, fields)

    assert read is not None
    assert read.rounds == fields[USAGE_ROUNDS_KEY]
    assert read.by_model == {}
    assert USAGE_BY_MODEL_KEY in caplog.text
    assert str(_PATH) in caplog.text
