"""Load tests for reading token usage off every streamed chunk (slice 931 D8).

Required by ``.claude/rules/python.md``'s load-test tier and the slice design's event-loop
NFR: ``read_chunk_usage`` now runs synchronously on every chunk inside ``_stream_turn``,
an ``async`` function, so its per-call cost is paid on the event loop. A unit test cannot
see starvation; these run a realistically long stream beside a ticker task and assert the
loop keeps getting scheduled, and bound the reader's own per-call cost. Bounds are generous
so CI jitter does not fail them, and tight enough that a slow reader would.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from openai.types.chat import ChatCompletionChunk

from squadron.providers.openai.agent import OpenAICompatibleAgent
from squadron.providers.openai.usage import read_chunk_usage

CHUNK_COUNT = 5_000
MALFORMED_EVERY = 1_000
MAX_LOOP_GAP_S = 0.050
MAX_MEAN_READ_S = 0.001
READ_CALLS = 1_000

_USAGE = {
    "prompt_tokens": 400_000,
    "completion_tokens": 9_000,
    "total_tokens": 409_000,
    "prompt_tokens_details": {"cached_tokens": 380_000},
    "completion_tokens_details": {"reasoning_tokens": 6_000},
}


def _chunk(content: str, usage: dict[str, object] | None = None) -> ChatCompletionChunk:
    choices: list[dict[str, object]] = (
        []
        if usage is not None
        else [{"delta": {"content": content}, "finish_reason": None, "index": 0}]
    )
    return ChatCompletionChunk.construct(
        id="c",
        choices=choices,
        created=1700000000,
        model="m",
        object="chat.completion.chunk",
        usage=usage,
    )


def _stream_chunks() -> list[ChatCompletionChunk]:
    chunks = [_chunk("x ") for _ in range(CHUNK_COUNT - 1)]
    for index in range(0, CHUNK_COUNT - 1, MALFORMED_EVERY):
        chunks[index] = _chunk("", {**_USAGE, "prompt_tokens": "garbled"})
    chunks.append(_chunk("", _USAGE))
    return chunks


async def _yielding_stream(chunks: list[ChatCompletionChunk]) -> AsyncIterator[ChatCompletionChunk]:
    # A real stream awaits the network between chunks; the sleep(0) gives other tasks the
    # same chance to run, so a gap measures the reader's work, not the stub's.
    for chunk in chunks:
        await asyncio.sleep(0)
        yield chunk


async def test_long_stream_with_usage_does_not_starve_the_loop() -> None:
    client: Any = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=_yielding_stream(_stream_chunks()))
    agent = OpenAICompatibleAgent(
        name="load", client=client, model="m", system_prompt=None, max_tool_iterations=2
    )
    gaps: list[float] = []
    done = asyncio.Event()

    async def _ticker() -> None:
        last = time.monotonic()
        while not done.is_set():
            await asyncio.sleep(0)
            now = time.monotonic()
            gaps.append(now - last)
            last = now

    ticker = asyncio.create_task(_ticker())
    turn = await agent._stream_turn([], tool_schemas=None)  # pyright: ignore[reportPrivateUsage]
    done.set()
    await ticker

    assert turn.usage is not None
    assert turn.usage.prompt == 400_000
    assert gaps, "ticker never ran"
    assert max(gaps) < MAX_LOOP_GAP_S


def test_read_chunk_usage_mean_cost_is_under_a_millisecond() -> None:
    chunk = _chunk("", _USAGE)

    started = time.perf_counter()
    for _ in range(READ_CALLS):
        read_chunk_usage(chunk)
    mean = (time.perf_counter() - started) / READ_CALLS

    assert mean < MAX_MEAN_READ_S
