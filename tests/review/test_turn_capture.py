"""Tests for TurnCapture.answering_models folding (slice 927 C.5)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from squadron.core.models import Message, MessageType
from squadron.core.usage import RunTelemetry, TokenUsage
from squadron.providers.errors import EmptyFinalTurnError
from squadron.review.turn_capture import (
    TurnCapture,
    budget_exhausted,
    collect_turn,
    describe_budget,
    fold_empty_turn,
)


class _FakeAgent:
    """An agent whose handle_message yields Messages stamped like a real provider."""

    def __init__(self, replies: list[list[Message]]) -> None:
        self._replies = replies
        self._call = 0

    async def handle_message(self, message: Message) -> AsyncIterator[Message]:
        reply = self._replies[self._call]
        self._call += 1
        for msg in reply:
            yield msg


def _stamped(content: str, *, answering_models: list[str] | None = None, **extra: Any) -> Message:
    metadata: dict[str, Any] = dict(extra)
    if answering_models is not None:
        metadata["answering_models"] = answering_models
    return Message(
        sender="agent",
        recipients=["review-system"],
        content=content,
        message_type=MessageType.chat,
        metadata=metadata,
    )


@pytest.mark.asyncio
async def test_single_call_folds_stamped_models() -> None:
    agent = _FakeAgent([[_stamped("review text", answering_models=["gpt-4o"])]])
    capture = TurnCapture()

    await collect_turn(agent, content="go", recipient="bot", capture=capture)

    assert capture.answering_models == ["gpt-4o"]


@pytest.mark.asyncio
async def test_two_calls_combine_into_a_distinct_list() -> None:
    """Accumulates across the #92 recovery turn."""
    agent = _FakeAgent(
        [
            [_stamped("first", answering_models=["gpt-4o"])],
            [_stamped("second", answering_models=["gpt-4.1"])],
        ]
    )
    capture = TurnCapture()

    await collect_turn(agent, content="go", recipient="bot", capture=capture)
    await collect_turn(agent, content="finish", recipient="bot", capture=capture)

    assert capture.answering_models == ["gpt-4o", "gpt-4.1"]


@pytest.mark.asyncio
async def test_repeated_model_across_calls_stays_distinct() -> None:
    agent = _FakeAgent(
        [
            [_stamped("first", answering_models=["gpt-4o"])],
            [_stamped("second", answering_models=["gpt-4o"])],
        ]
    )
    capture = TurnCapture()

    await collect_turn(agent, content="go", recipient="bot", capture=capture)
    await collect_turn(agent, content="finish", recipient="bot", capture=capture)

    assert capture.answering_models == ["gpt-4o"]


@pytest.mark.asyncio
async def test_turn_with_no_stamp_leaves_the_list_unchanged() -> None:
    agent = _FakeAgent([[_stamped("no models here")]])
    capture = TurnCapture(answering_models=["gpt-4o"])

    await collect_turn(agent, content="go", recipient="bot", capture=capture)

    assert capture.answering_models == ["gpt-4o"]


@pytest.mark.parametrize("stop_reason", ["length", "max_tokens"])
def test_budget_exhausted_on_budget_stop_reasons(stop_reason: str) -> None:
    assert budget_exhausted(stop_reason) is True


@pytest.mark.parametrize("stop_reason", ["stop", "end_turn", "tool_calls", None])
def test_budget_not_exhausted_on_other_stop_reasons(stop_reason: str | None) -> None:
    assert budget_exhausted(stop_reason) is False


def test_describe_budget_names_the_sent_budget() -> None:
    assert describe_budget(32000) == "32000 tokens"


def test_describe_budget_names_the_backend_default_when_none_was_sent() -> None:
    assert describe_budget(None) == "backend default"


# --- turns and usage (slice 931 D8) ---


def _empty_turn_error(telemetry: RunTelemetry | None) -> EmptyFinalTurnError:
    error = EmptyFinalTurnError(
        "empty", finish_reason="length", reasoning_chars=40, tool_calls_made=1, failed_tool_calls=0
    )
    # Attached after construction, as the agent's handler does.
    error.telemetry = telemetry
    return error


@pytest.mark.asyncio
async def test_empty_turn_then_recovery_sums_turns_usage_and_run_reasoning() -> None:
    capture = TurnCapture()
    fold_empty_turn(
        capture,
        _empty_turn_error(
            RunTelemetry(turns=3, reasoning_chars=100, usage=TokenUsage(prompt=30, completion=3))
        ),
    )
    agent = _FakeAgent(
        [
            [
                _stamped(
                    "review",
                    turns=2,
                    reasoning_chars=10,
                    usage=TokenUsage(prompt=50, cached=20, completion=5),
                )
            ]
        ]
    )

    await collect_turn(agent, content="finish", recipient="r", capture=capture)

    assert capture.turns == 5
    assert capture.usage == TokenUsage(prompt=80, cached=20, completion=8, reasoning=None)
    # The run totals (100 + 10), not the empty turn's own 40.
    assert capture.reasoning_chars == 110


@pytest.mark.asyncio
async def test_two_calls_sum_turns_and_usage() -> None:
    capture = TurnCapture()
    agent = _FakeAgent(
        [
            [_stamped("a", turns=1, usage=TokenUsage(prompt=5))],
            [_stamped("b", turns=2, usage=TokenUsage(prompt=7, reasoning=1))],
        ]
    )

    await collect_turn(agent, content="x", recipient="r", capture=capture)
    await collect_turn(agent, content="y", recipient="r", capture=capture)

    assert capture.turns == 3
    assert capture.usage == TokenUsage(prompt=12, reasoning=1)


def test_error_without_telemetry_folds_as_before() -> None:
    capture = TurnCapture()

    fold_empty_turn(capture, _empty_turn_error(None))

    assert capture.reasoning_chars == 40
    assert capture.turns is None
    assert capture.usage == TokenUsage()


@pytest.mark.asyncio
async def test_provider_that_stamps_no_usage_leaves_fields_unreported() -> None:
    capture = TurnCapture()

    await collect_turn(_FakeAgent([[_stamped("a")]]), content="x", recipient="r", capture=capture)

    assert capture.turns is None
    assert capture.usage == TokenUsage()
