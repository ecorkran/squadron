"""``stamp_effort_sent`` and the strict effort readers (slice 420 D5)."""

from __future__ import annotations

import json
from typing import cast

import pytest

from squadron.core.models import Effort
from squadron.core.usage import TokenUsage, UsageRecord
from squadron.pipeline import usage_capture
from squadron.pipeline.usage_capture import (
    EFFORT_SENT_KEY,
    action_effort_sent,
    effort_sent_by_profile,
    note_effort_sent,
    read_effort_sent,
    stamp_effort_sent,
)


def _usage(effort: str | None) -> UsageRecord:
    return UsageRecord(
        model="m",
        alias="a",
        profile="p",
        effort=effort,
        turns=1,
        duration_seconds=1.0,
        usage=TokenUsage(),
        cost_usd=None,
        cost_basis=None,
    )


def _round_trip(metadata: dict[str, object]) -> dict[str, object]:
    return cast(dict[str, object], json.loads(json.dumps(metadata)))


@pytest.mark.parametrize("effort", [Effort.high, Effort.none, None])
def test_stamp_then_read_survives_json(effort: Effort | None) -> None:
    metadata: dict[str, object] = {}
    stamp_effort_sent(metadata, effort)

    assert action_effort_sent(_round_trip(metadata), None) is effort


@pytest.mark.parametrize("stored", ["HIGH", "  low "])
def test_stored_value_ignores_case_and_padding(stored: str) -> None:
    assert action_effort_sent({EFFORT_SENT_KEY: stored}, None) is Effort(stored.strip().lower())


def test_absent_key_falls_back_to_usage_effort() -> None:
    assert action_effort_sent({}, _usage("medium")) is Effort.medium


def test_absent_key_without_usage_is_none() -> None:
    assert action_effort_sent({}, None) is None


def test_stamp_wins_over_differing_usage_effort() -> None:
    assert action_effort_sent({EFFORT_SENT_KEY: "low"}, _usage("high")) is Effort.low


def test_stamped_none_wins_over_usage_effort() -> None:
    assert action_effort_sent({EFFORT_SENT_KEY: None}, _usage("high")) is None


def test_unrecognized_string_raises_from_both_readers() -> None:
    with pytest.raises(ValueError, match="bogus"):
        action_effort_sent({EFFORT_SENT_KEY: "bogus"}, None)
    with pytest.raises(ValueError, match="bogus"):
        read_effort_sent({EFFORT_SENT_KEY: "bogus"})


def test_read_effort_sent_raises_on_other_types() -> None:
    with pytest.raises(ValueError, match="3"):
        read_effort_sent({EFFORT_SENT_KEY: 3})


def test_read_effort_sent_absent_key_is_none() -> None:
    assert read_effort_sent({}) is None


def test_gate_off_sends_no_effort(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Capabilities:
        applies_effort = False

    class _Provider:
        capabilities = _Capabilities()

    class _Profile:
        provider = "fake"

    monkeypatch.setattr(usage_capture, "get_profile", lambda _name: _Profile())
    monkeypatch.setattr(usage_capture, "ensure_provider_loaded", lambda _name: None)
    monkeypatch.setattr(usage_capture, "get_provider", lambda _name: _Provider())
    metadata: dict[str, object] = {}

    note_effort_sent(metadata, Effort.high, applies_effort=False)

    assert read_effort_sent(metadata) is None
    assert effort_sent_by_profile("any", Effort.high) is None
