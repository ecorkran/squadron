"""Tests for TurnCapture.answering_models folding (slice 927 C.5)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from squadron.core.models import Message, MessageType
from squadron.review.turn_capture import TurnCapture, collect_turn


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
