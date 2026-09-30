"""Shared fixtures and factories for OpenAI provider tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from openai.types.chat import ChatCompletionChunk
from openai.types.chat.chat_completion_chunk import (
    Choice,
    ChoiceDelta,
    ChoiceDeltaToolCall,
    ChoiceDeltaToolCallFunction,
)


@pytest.fixture
def mock_async_openai() -> MagicMock:
    """MagicMock of AsyncOpenAI with streaming create and close as AsyncMocks."""
    client = MagicMock()
    client.chat.completions.create = AsyncMock()
    client.close = AsyncMock()
    return client


def text_chunk(content: str) -> ChatCompletionChunk:
    """Minimal ChatCompletionChunk with text delta content."""
    return ChatCompletionChunk(
        id="chunk-1",
        choices=[
            Choice(
                delta=ChoiceDelta(content=content, tool_calls=None),
                finish_reason=None,
                index=0,
            )
        ],
        created=1700000000,
        model="gpt-4o",
        object="chat.completion.chunk",
    )


def tool_chunk(
    index: int,
    id: str,
    name: str,
    args_fragment: str,
) -> ChatCompletionChunk:
    """ChatCompletionChunk carrying a tool_calls delta."""
    return ChatCompletionChunk(
        id="chunk-1",
        choices=[
            Choice(
                delta=ChoiceDelta(
                    content=None,
                    tool_calls=[
                        ChoiceDeltaToolCall(
                            index=index,
                            id=id,
                            type="function",
                            function=ChoiceDeltaToolCallFunction(
                                name=name,
                                arguments=args_fragment,
                            ),
                        )
                    ],
                ),
                finish_reason=None,
                index=0,
            )
        ],
        created=1700000000,
        model="gpt-4o",
        object="chat.completion.chunk",
    )


def usage_chunk(usage: dict[str, object], *, openrouter_shape: bool = False) -> ChatCompletionChunk:
    """A usage-bearing chunk as a backend sends it with ``include_usage`` (slice 931 D8).

    OpenAI and Ollama send usage on a chunk with no choices; OpenRouter sends one empty
    choice. Built with ``construct`` — the SDK's own unvalidated path — so malformed
    values reach the reader exactly as a misbehaving backend would deliver them.
    """
    choices: list[dict[str, object]] = (
        [{"delta": {}, "finish_reason": None, "index": 0}] if openrouter_shape else []
    )
    return ChatCompletionChunk.construct(
        id="chunk-usage",
        choices=choices,
        created=1700000000,
        model="gpt-4o",
        object="chat.completion.chunk",
        usage=usage,
    )
