"""Tests for the OpenAICompatibleAgent agentic loop: constructor tool-set wiring,
loop control flow, and their termination/error-surfacing behavior.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from openai import omit

from squadron.core.models import Message, MessageType
from squadron.providers.errors import ProviderError
from squadron.providers.openai.agent import (
    OpenAICompatibleAgent,
    TurnResult,
    _entry_chars,  # pyright: ignore[reportPrivateUsage]
)
from squadron.tools import ToolResult

from .conftest import text_chunk, tool_chunk

_MODEL = "gpt-4o-mini"
_USER_MSG = Message(sender="human", recipients=["bot"], content="hello")


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
    max_tool_iterations: int | None = None,
    max_history_chars: int | None = None,
) -> OpenAICompatibleAgent:
    # Loop bounds are injected, not read from config: the agent resolves them at
    # construction time (in the provider), so no test touches the real user config.
    return OpenAICompatibleAgent(
        name="bot",
        client=client if client is not None else _make_client(),
        model=_MODEL,
        system_prompt=None,
        allowed_tools=allowed_tools,
        cwd=cwd,
        max_tool_iterations=max_tool_iterations,
        max_history_chars=max_history_chars,
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
        # omit is the SDK's "parameter not sent" sentinel — it is dropped from the
        # wire payload, unlike an explicit tools=None.
        assert kwargs["tools"] is omit

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


def _tool_call(tool_call_id: str, name: str, arguments: str) -> dict[str, Any]:
    return {
        "id": tool_call_id,
        "type": "function",
        "function": {"name": name, "arguments": arguments},
    }


class TestExecuteToolCall:
    @pytest.mark.asyncio
    async def test_malformed_json_args_returns_error_and_logs_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.WARNING)
        agent = _make_agent()
        tc = _tool_call("c1", "read_file", "{not json")
        content = await agent._execute_tool_call(tc)  # pyright: ignore[reportPrivateUsage]
        assert "not valid JSON" in content
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1
        assert "read_file" in warnings[0].getMessage()

    @pytest.mark.asyncio
    async def test_unknown_tool_name_returns_error_and_logs_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.WARNING)
        agent = _make_agent()
        tc = _tool_call("c1", "no_such_tool", "{}")
        content = await agent._execute_tool_call(tc)  # pyright: ignore[reportPrivateUsage]
        assert "no_such_tool" in content
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1

    @pytest.mark.asyncio
    async def test_executor_error_result_passed_through_verbatim(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.INFO)
        agent = _make_agent()
        agent._tool_executors["boom_tool"] = AsyncMock(  # pyright: ignore[reportPrivateUsage]
            return_value=ToolResult(content="boom", is_error=True)
        )
        tc = _tool_call("c1", "boom_tool", "{}")
        content = await agent._execute_tool_call(tc)  # pyright: ignore[reportPrivateUsage]
        assert content == "boom"
        assert any(r.levelno == logging.INFO for r in caplog.records)
        assert not any(r.levelno == logging.WARNING for r in caplog.records)

    @pytest.mark.asyncio
    async def test_executor_raises_returns_error_and_logs_error(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.ERROR)

        async def _raising(_args: dict[str, object]) -> ToolResult:
            raise RuntimeError("kaboom")

        agent = _make_agent()
        agent._tool_executors["raising_tool"] = _raising  # pyright: ignore[reportPrivateUsage]
        tc = _tool_call("c1", "raising_tool", "{}")
        content = await agent._execute_tool_call(tc)  # pyright: ignore[reportPrivateUsage]
        assert "raising_tool" in content
        errors = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(errors) == 1

    @pytest.mark.asyncio
    async def test_executor_success_returns_content_and_logs_debug(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.DEBUG)
        agent = _make_agent()
        agent._tool_executors["ok_tool"] = AsyncMock(  # pyright: ignore[reportPrivateUsage]
            return_value=ToolResult(content="the answer")
        )
        tc = _tool_call("c1", "ok_tool", "{}")
        content = await agent._execute_tool_call(tc)  # pyright: ignore[reportPrivateUsage]
        assert content == "the answer"
        assert any(r.levelno == logging.DEBUG for r in caplog.records)


async def _collect(agent: OpenAICompatibleAgent, msg: Message) -> list[Message]:
    return [m async for m in agent.handle_message(msg)]


class TestAgenticLoop:
    @pytest.mark.asyncio
    async def test_normal_termination_suppresses_intermediate_turn(self, tmp_path: Path) -> None:
        write_call = tool_chunk(
            0, "call_1", "write_file", json.dumps({"path": "out.txt", "content": "hi"})
        )
        client = _make_client()
        client.chat.completions.create = AsyncMock(
            side_effect=[
                _async_stream(write_call),
                _async_stream(text_chunk("all done")),
            ]
        )
        agent = _make_agent(allowed_tools=["write_file"], cwd=str(tmp_path), client=client)
        msgs = await _collect(agent, _USER_MSG)

        assert client.chat.completions.create.call_count == 2
        assert len(msgs) == 1
        assert msgs[0].message_type == MessageType.chat
        assert msgs[0].content == "all done"
        assert not any(m.message_type == MessageType.system for m in msgs)
        assert (tmp_path / "out.txt").read_text() == "hi"

    @pytest.mark.asyncio
    async def test_multi_tool_single_turn_dispatches_all_in_order(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("A")
        (tmp_path / "b.txt").write_text("B")
        call_a = tool_chunk(0, "call_a", "read_file", json.dumps({"path": "a.txt"}))
        call_b = tool_chunk(1, "call_b", "read_file", json.dumps({"path": "b.txt"}))
        client = _make_client()
        client.chat.completions.create = AsyncMock(
            side_effect=[
                _async_stream(call_a, call_b),
                _async_stream(text_chunk("read both")),
            ]
        )
        agent = _make_agent(allowed_tools=["read_file"], cwd=str(tmp_path), client=client)
        msgs = await _collect(agent, _USER_MSG)

        assert client.chat.completions.create.call_count == 2
        assert len(msgs) == 1
        assert msgs[0].content == "read both"

        history = agent._history  # pyright: ignore[reportPrivateUsage]
        tool_entries = [e for e in history if e["role"] == "tool"]
        assert len(tool_entries) == 2
        assert tool_entries[0]["tool_call_id"] == "call_a"
        assert tool_entries[1]["tool_call_id"] == "call_b"
        assert "A" in tool_entries[0]["content"]
        assert "B" in tool_entries[1]["content"]

    @pytest.mark.asyncio
    async def test_max_iterations_guard_raises_and_logs_warning(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        caplog.set_level(logging.WARNING)
        # Every turn calls a tool — the loop never finalizes.
        never_ending_call = tool_chunk(0, "call_1", "read_file", json.dumps({"path": "a.txt"}))
        (tmp_path / "a.txt").write_text("A")
        client = _make_client()
        client.chat.completions.create = AsyncMock(return_value=_async_stream(never_ending_call))
        agent = _make_agent(
            allowed_tools=["read_file"],
            cwd=str(tmp_path),
            client=client,
            max_tool_iterations=2,
        )

        with pytest.raises(ProviderError):
            await _collect(agent, _USER_MSG)

        assert client.chat.completions.create.call_count == 2
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert any("max_tool_iterations" in r.getMessage() for r in warnings)

    @pytest.mark.asyncio
    async def test_history_budget_guard_fires_once_and_continues(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        caplog.set_level(logging.WARNING)
        (tmp_path / "a.txt").write_text("A")
        read_call = tool_chunk(0, "call_1", "read_file", json.dumps({"path": "a.txt"}))
        client = _make_client()
        client.chat.completions.create = AsyncMock(
            side_effect=[
                _async_stream(read_call),
                _async_stream(read_call),
                _async_stream(text_chunk("done")),
            ]
        )
        agent = _make_agent(
            allowed_tools=["read_file"],
            cwd=str(tmp_path),
            client=client,
            max_history_chars=10,
        )
        msgs = await _collect(agent, _USER_MSG)

        assert len(msgs) == 1
        assert msgs[0].content == "done"
        history = agent._history  # pyright: ignore[reportPrivateUsage]
        # A plain user-role notice, not a fake tool result: a role:"tool" entry must
        # carry a tool_call_id matching a real pending call, which this isn't.
        budget_entries = [
            e
            for e in history
            if e.get("role") == "user" and "budget" in str(e.get("content", "")).lower()
        ]
        assert len(budget_entries) == 1
        assert not any(e.get("role") == "tool" and e.get("tool_call_id") == "" for e in history)
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        budget_warnings = [r for r in warnings if "max_history_chars" in r.getMessage()]
        assert len(budget_warnings) == 1

        # Once the guard has fired, no more tool schemas are offered — the notice
        # asks the model to finalize, and continuing to advertise tools would let it
        # ignore that and keep calling them anyway.
        last_call_kwargs = client.chat.completions.create.call_args_list[-1].kwargs
        assert last_call_kwargs["tools"] is omit

    @pytest.mark.asyncio
    async def test_append_only_history_is_strict_prefix_extension(self, tmp_path: Path) -> None:
        # _stream_turn is called with self._history by reference, so Mock's
        # call_args_list holds the *same* list object across calls (it grows
        # in place). Snapshot a deep copy at call time via side_effect.
        (tmp_path / "a.txt").write_text("A")
        read_call = tool_chunk(0, "call_1", "read_file", json.dumps({"path": "a.txt"}))
        streams = [
            _async_stream(read_call),
            _async_stream(read_call),
            _async_stream(text_chunk("done")),
        ]
        snapshots: list[list[dict[str, Any]]] = []

        async def _create(**kwargs: Any) -> Any:
            snapshots.append([dict(e) for e in kwargs["messages"]])
            return streams[len(snapshots) - 1]

        client = _make_client()
        client.chat.completions.create = AsyncMock(side_effect=_create)
        agent = _make_agent(allowed_tools=["read_file"], cwd=str(tmp_path), client=client)
        await _collect(agent, _USER_MSG)

        assert len(snapshots) == 3
        for earlier, later in zip(snapshots, snapshots[1:], strict=False):
            assert later[: len(earlier)] == earlier
            assert len(later) > len(earlier)

    @pytest.mark.asyncio
    async def test_tools_configured_but_unused_returns_plain_text(self, tmp_path: Path) -> None:
        client = _make_client()
        client.chat.completions.create = AsyncMock(
            return_value=_async_stream(text_chunk("no tools needed"))
        )
        agent = _make_agent(allowed_tools=["read_file"], cwd=str(tmp_path), client=client)
        msgs = await _collect(agent, _USER_MSG)

        assert client.chat.completions.create.call_count == 1
        assert len(msgs) == 1
        assert msgs[0].content == "no tools needed"

    @pytest.mark.asyncio
    async def test_tool_call_without_id_raises_without_executing_tool(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        # An OpenAI-*compatible* backend may stream a tool call with no id. Its result
        # could never be matched back to the call, so the loop must abort rather than
        # run a side effect whose output is undeliverable and poison history.
        caplog.set_level(logging.WARNING)
        idless_call = tool_chunk(0, "", "write_file", json.dumps({"path": "x.txt", "content": "z"}))
        client = _make_client()
        client.chat.completions.create = AsyncMock(return_value=_async_stream(idless_call))
        agent = _make_agent(allowed_tools=["write_file"], cwd=str(tmp_path), client=client)

        with pytest.raises(ProviderError, match="no id"):
            await _collect(agent, _USER_MSG)

        # The side-effecting tool must not have run.
        assert not (tmp_path / "x.txt").exists()
        # No unmatched tool result was appended to history.
        history = agent._history  # pyright: ignore[reportPrivateUsage]
        assert not any(e.get("role") == "tool" for e in history)
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert any("no id" in r.getMessage() for r in warnings)

    @pytest.mark.asyncio
    async def test_history_char_counter_matches_full_rescan(self, tmp_path: Path) -> None:
        # The running counter replaces an O(n^2) per-iteration rescan, so it must stay
        # exactly in step with what a fresh scan of the final history would produce.
        (tmp_path / "a.txt").write_text("A" * 50)
        read_call = tool_chunk(0, "call_1", "read_file", json.dumps({"path": "a.txt"}))
        client = _make_client()
        client.chat.completions.create = AsyncMock(
            side_effect=[
                _async_stream(read_call),
                _async_stream(read_call),
                _async_stream(text_chunk("done")),
            ]
        )
        agent = _make_agent(allowed_tools=["read_file"], cwd=str(tmp_path), client=client)
        await _collect(agent, _USER_MSG)

        history = agent._history  # pyright: ignore[reportPrivateUsage]
        expected = sum(_entry_chars(e) for e in history)
        assert agent._history_chars == expected  # pyright: ignore[reportPrivateUsage]
        assert expected > 0

    @pytest.mark.asyncio
    async def test_non_object_json_args_returns_error_and_logs_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        # Valid JSON that isn't an object still can't be splatted into an executor,
        # which takes a keyword mapping.
        caplog.set_level(logging.WARNING)
        agent = _make_agent(allowed_tools=["read_file"], cwd=str(tmp_path))
        tc = _tool_call("c1", "read_file", "[1, 2]")
        content = await agent._execute_tool_call(tc)  # pyright: ignore[reportPrivateUsage]

        assert "must be a JSON object" in content
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert any("not a JSON object" in r.getMessage() for r in warnings)
