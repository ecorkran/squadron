"""Tests for the SDK ``ResultMessage`` usage reader (slice 175 D1, D2)."""

from __future__ import annotations

import logging
from typing import Any

import pytest

from squadron.core.usage import TokenUsage
from squadron.providers.sdk.usage import SessionCostMeter, read_result_usage
from tests.providers.sdk.result_fixture import real_result_fields, real_result_message


def test_real_fixture_maps_to_d1_sums() -> None:
    fields = real_result_fields()
    usage: dict[str, Any] = fields["usage"]

    tokens, turns, cost = read_result_usage(real_result_message())

    assert tokens == TokenUsage(
        prompt=usage["input_tokens"]
        + usage["cache_read_input_tokens"]
        + usage["cache_creation_input_tokens"],
        cached=usage["cache_read_input_tokens"],
        cache_write=usage["cache_creation_input_tokens"],
        completion=usage["output_tokens"],
        reasoning=None,
    )
    assert turns == fields["num_turns"]
    assert cost == fields["total_cost_usd"]


def test_no_cache_keys_leave_cache_fields_none() -> None:
    msg = real_result_message(usage={"input_tokens": 40, "output_tokens": 3})

    tokens, _, _ = read_result_usage(msg)

    assert tokens == TokenUsage(prompt=40, cached=None, cache_write=None, completion=3)


def test_missing_input_tokens_leaves_prompt_none() -> None:
    msg = real_result_message(usage={"cache_read_input_tokens": 9, "output_tokens": 3})

    tokens, _, _ = read_result_usage(msg)

    assert tokens is not None
    assert tokens.prompt is None
    assert tokens.cached == 9


def test_usage_none_still_reads_turns_and_cost() -> None:
    msg = real_result_message(usage=None, num_turns=4, total_cost_usd=0.5)

    assert read_result_usage(msg) == (None, 4, 0.5)


def test_malformed_value_is_none_with_warning(caplog: pytest.LogCaptureFixture) -> None:
    msg = real_result_message(
        usage={"input_tokens": 10, "cache_read_input_tokens": "12", "output_tokens": 2}
    )

    with caplog.at_level(logging.WARNING, logger="squadron.providers.sdk.usage"):
        tokens, _, _ = read_result_usage(msg)

    assert tokens == TokenUsage(prompt=10, cached=None, completion=2)
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "cache_read_input_tokens" in warnings[0]


def test_bool_count_is_not_an_int() -> None:
    msg = real_result_message(usage={"input_tokens": True, "output_tokens": 2})

    tokens, _, _ = read_result_usage(msg)

    assert tokens is not None and tokens.prompt is None


def test_wrong_typed_turns_and_cost_read_as_none() -> None:
    msg = real_result_message(num_turns="3", total_cost_usd="0.1")

    _, turns, cost = read_result_usage(msg)

    assert turns is None and cost is None


class TestSessionCostMeter:
    def test_charges_the_increase_since_the_last_total(self) -> None:
        meter = SessionCostMeter()

        assert meter.charge(4.73) == pytest.approx(4.73)
        assert meter.charge(5.34) == pytest.approx(0.61)

    def test_unreported_total_charges_nothing_and_keeps_the_baseline(self) -> None:
        meter = SessionCostMeter()
        meter.charge(1.0)

        assert meter.charge(None) is None
        assert meter.charge(1.5) == pytest.approx(0.5)

    def test_a_lower_total_is_a_reset_and_is_charged_in_full(self) -> None:
        meter = SessionCostMeter()
        meter.charge(3.0)

        assert meter.charge(0.4) == pytest.approx(0.4)
