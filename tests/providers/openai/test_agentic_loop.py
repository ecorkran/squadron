"""Tests for the OpenAICompatibleAgent agentic loop: constructor tool-set wiring,
loop control flow, and their termination/error-surfacing behavior.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadron.providers.errors import ProviderError
from squadron.providers.openai.agent import OpenAICompatibleAgent, TurnResult

from .conftest import text_chunk, tool_chunk

_MODEL = "gpt-4o-mini"


def _make_client() -> Any:
    client = MagicMock()
    client.chat.completions.create = AsyncMock()
    client.close = AsyncMock()
    return client


def _make_agent(
    *,
    allowed_tools: list[str] | None = None,
    cwd: str | None = None,
    client: Any = None,
) -> OpenAICompatibleAgent:
    return OpenAICompatibleAgent(
        name="bot",
        client=client if client is not None else _make_client(),
        model=_MODEL,
        system_prompt=None,
        allowed_tools=allowed_tools,
        cwd=cwd,
    )


class TestConstructorToolSetWiring:
    def test_no_tools_no_cwd_does_not_raise_and_is_empty(self) -> None:
        agent = _make_agent(allowed_tools=None, cwd=None)
        assert agent._tool_executors == {}  # pyright: ignore[reportPrivateUsage]
        assert agent._tool_schemas == []  # pyright: ignore[reportPrivateUsage]

    def test_empty_list_tools_no_cwd_does_not_raise(self) -> None:
        agent = _make_agent(allowed_tools=[], cwd=None)
        assert agent._tool_executors == {}  # pyright: ignore[reportPrivateUsage]

    def test_known_tool_with_cwd_materializes_no_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.WARNING)
        agent = _make_agent(allowed_tools=["read_file"], cwd=str(tmp_path))
        assert "read_file" in agent._tool_executors  # pyright: ignore[reportPrivateUsage]
        assert not any(r.levelno == logging.WARNING for r in caplog.records)

    def test_mixed_known_and_unknown_drops_unknown_with_one_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.WARNING)
        agent = _make_agent(allowed_tools=["Read", "read_file"], cwd=str(tmp_path))
        executors = agent._tool_executors  # pyright: ignore[reportPrivateUsage]
        assert "read_file" in executors
        assert "Read" not in executors
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1
        assert "Read" in warnings[0].getMessage()

    def test_known_tool_no_cwd_raises_provider_error(self) -> None:
        with pytest.raises(ProviderError):
            _make_agent(allowed_tools=["read_file"], cwd=None)

    def test_only_unknown_tools_no_cwd_raises_provider_error(self) -> None:
        # D8 checks the requested set, not the post-filter set (Constraint 3):
        # a caller requesting only unknown names with no cwd must still be refused.
        with pytest.raises(ProviderError):
            _make_agent(allowed_tools=["Read"], cwd=None)


def _async_stream(*chunks: Any) -> AsyncMock:
    """Return an AsyncMock whose __aiter__ yields the given chunks."""

    async def _gen() -> Any:
        for chunk in chunks:
            yield chunk

    mock = AsyncMock()
    mock.__aiter__ = lambda _: _gen()
    return mock


class TestStreamTurn:
    @pytest.mark.asyncio
    async def test_text_only_stream_returns_text_result(self) -> None:
        client = _make_client()
        client.chat.completions.create = AsyncMock(return_value=_async_stream(text_chunk("hi")))
        agent = _make_agent(client=client)
        result = await agent._stream_turn([], tool_schemas=None)  # pyright: ignore[reportPrivateUsage]
        assert result == TurnResult(text="hi", tool_calls=[])

    @pytest.mark.asyncio
    async def test_tool_call_stream_returns_assembled_call(self) -> None:
        client = _make_client()
        chunk = tool_chunk(0, "call_1", "search", '{"q": "hi"}')
        client.chat.completions.create = AsyncMock(return_value=_async_stream(chunk))
        agent = _make_agent(client=client)
        result = await agent._stream_turn([], tool_schemas=None)  # pyright: ignore[reportPrivateUsage]
        assert result.text == ""
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["id"] == "call_1"
        assert result.tool_calls[0]["function"]["name"] == "search"
        assert result.tool_calls[0]["function"]["arguments"] == '{"q": "hi"}'

    @pytest.mark.asyncio
    async def test_no_tools_kwarg_when_tool_schemas_none(self) -> None:
        client = _make_client()
        client.chat.completions.create = AsyncMock(return_value=_async_stream(text_chunk("hi")))
        agent = _make_agent(client=client)
        await agent._stream_turn([], tool_schemas=None)  # pyright: ignore[reportPrivateUsage]
        _, kwargs = client.chat.completions.create.call_args
        assert "tools" not in kwargs

    @pytest.mark.asyncio
    async def test_tools_kwarg_present_when_tool_schemas_given(self) -> None:
        client = _make_client()
        client.chat.completions.create = AsyncMock(return_value=_async_stream(text_chunk("hi")))
        agent = _make_agent(client=client)
        schemas = [
            {"type": "function", "function": {"name": "t", "description": "d", "parameters": {}}}
        ]
        await agent._stream_turn([], tool_schemas=schemas)  # pyright: ignore[reportPrivateUsage]
        _, kwargs = client.chat.completions.create.call_args
        assert kwargs["tools"] == schemas
