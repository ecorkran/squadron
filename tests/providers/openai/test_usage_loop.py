"""Per-turn and per-run token usage in the OpenAI agent (slice 931 D8, D12)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import openai
import pytest

from squadron.core.models import Effort, Message
from squadron.core.usage import TokenUsage
from squadron.providers.errors import (
    EmptyFinalTurnError,
    ProviderAPIError,
    ProviderError,
    ProviderTimeoutError,
)
from squadron.providers.openai.agent import OpenAICompatibleAgent

from .conftest import async_stream, text_chunk, tool_chunk, usage_chunk

_USER_MSG = Message(sender="human", recipients=["bot"], content="hello")


def _usage(prompt: int, completion: int, *, cached: int = 0, reasoning: int = 0) -> dict[str, object]:
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": prompt + completion,
        "prompt_tokens_details": {"cached_tokens": cached},
        "completion_tokens_details": {"reasoning_tokens": reasoning},
    }


def _agent(
    *streams: Any,
    cwd: str | None = None,
    tools: list[str] | None = None,
    max_tool_iterations: int = 10,
    sends_stream_usage: bool = True,
    effort: Effort | None = None,
) -> OpenAICompatibleAgent:
    client = MagicMock()
    client.chat.completions.create = AsyncMock(side_effect=list(streams))
    client.close = AsyncMock()
    return OpenAICompatibleAgent(
        name="bot",
        client=client,
        model="gpt-4o-mini",
        system_prompt=None,
        allowed_tools=tools,
        cwd=cwd,
        max_tool_iterations=max_tool_iterations,
        max_history_chars=10_000_000,
        sends_stream_usage=sends_stream_usage,
        effort=effort,
    )


async def _collect(agent: OpenAICompatibleAgent) -> list[Message]:
    return [m async for m in agent.handle_message(_USER_MSG)]


class TestStreamTurnUsage:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("openrouter_shape", [False, True], ids=["openai-ollama", "openrouter"])
    async def test_both_shapes_yield_usage_with_text_and_tool_calls_intact(
        self, openrouter_shape: bool
    ) -> None:
        agent = _agent(
            async_stream(
                text_chunk("hel"),
                tool_chunk(0, "c1", "read_file", '{"path": "a"}'),
                text_chunk("lo"),
                usage_chunk(_usage(10, 3, cached=4, reasoning=1), openrouter_shape=openrouter_shape),
            )
        )

        turn = await agent._stream_turn([], tool_schemas=None)  # pyright: ignore[reportPrivateUsage]

        assert turn.usage == TokenUsage(prompt=10, cached=4, completion=3, reasoning=1)
        assert turn.text == "hello"
        assert [tc["function"]["name"] for tc in turn.tool_calls] == ["read_file"]

    @pytest.mark.asyncio
    async def test_last_usage_chunk_wins(self) -> None:
        agent = _agent(
            async_stream(text_chunk("x"), usage_chunk(_usage(1, 1)), usage_chunk(_usage(9, 9)))
        )

        turn = await agent._stream_turn([], tool_schemas=None)  # pyright: ignore[reportPrivateUsage]

        assert turn.usage is not None
        assert turn.usage.prompt == 9

    @pytest.mark.asyncio
    async def test_stream_without_usage_completes_with_none(self) -> None:
        agent = _agent(async_stream(text_chunk("hi")))

        turn = await agent._stream_turn([], tool_schemas=None)  # pyright: ignore[reportPrivateUsage]

        assert turn.usage is None
        assert turn.text == "hi"


def _reasoning_chunk(reasoning: str, content: str | None = None) -> Any:
    from openai.types.chat import ChatCompletionChunk

    delta: dict[str, object] = {"reasoning": reasoning}
    if content is not None:
        delta["content"] = content
    return ChatCompletionChunk.model_validate(
        {
            "id": "c",
            "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
            "created": 1700000000,
            "model": "m",
            "object": "chat.completion.chunk",
        }
    )


def _read_call(call_id: str) -> Any:
    return tool_chunk(0, call_id, "read_file", '{"path": "a.txt"}')


class TestRunAccumulation:
    @pytest.mark.asyncio
    async def test_three_turn_loop_sums_turns_usage_and_reasoning(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("A")
        agent = _agent(
            async_stream(
                _reasoning_chunk("abcd"),
                _read_call("c1"),
                usage_chunk(_usage(10, 2, cached=0, reasoning=3)),
            ),
            async_stream(
                _reasoning_chunk("ef"),
                _read_call("c2"),
                usage_chunk(_usage(20, 4, cached=8, reasoning=5)),
            ),
            async_stream(
                _reasoning_chunk("g", content="done"),
                usage_chunk(_usage(30, 6, cached=16, reasoning=7)),
            ),
            cwd=str(tmp_path),
            tools=["read_file"],
        )

        metadata = (await _collect(agent))[-1].metadata

        assert metadata["turns"] == 3
        assert metadata["usage"] == TokenUsage(prompt=60, cached=24, completion=12, reasoning=15)
        # The run's total, not the final turn's 1.
        assert metadata["reasoning_chars"] == 7

    @pytest.mark.asyncio
    async def test_partial_reporting_keeps_unreported_fields_none(self) -> None:
        agent = _agent(
            async_stream(
                text_chunk("hi"),
                usage_chunk({"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6}),
            )
        )

        usage = (await _collect(agent))[-1].metadata["usage"]

        assert usage == TokenUsage(prompt=5, cached=None, completion=1, reasoning=None)

    @pytest.mark.asyncio
    async def test_no_tools_run_stamps_turns_and_usage(self) -> None:
        agent = _agent(async_stream(text_chunk("hi"), usage_chunk(_usage(5, 1))))

        metadata = (await _collect(agent))[-1].metadata

        assert "tools_given" not in metadata
        assert metadata["turns"] == 1
        assert metadata["usage"].prompt == 5

    @pytest.mark.asyncio
    async def test_consecutive_calls_do_not_leak_telemetry(self) -> None:
        agent = _agent(
            async_stream(_reasoning_chunk("abc", content="one"), usage_chunk(_usage(5, 1))),
            async_stream(text_chunk("two")),
        )

        await _collect(agent)
        second = (await _collect(agent))[-1].metadata

        assert second["turns"] == 1
        assert second["usage"] == TokenUsage()
        assert second["reasoning_chars"] == 0


_NO_USAGE = "backend reported no token usage"
_EXIT = "OpenAI agent ended without a final response"


def _warnings(caplog: pytest.LogCaptureFixture, fragment: str) -> list[str]:
    return [
        r.getMessage()
        for r in caplog.records
        if r.levelno == logging.WARNING and fragment in r.getMessage()
    ]


class TestRunSignals:
    @pytest.mark.asyncio
    async def test_no_usage_warns_once_per_call_across_three_turns(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        (tmp_path / "a.txt").write_text("A")
        agent = _agent(
            async_stream(_read_call("c1")),
            async_stream(_read_call("c2")),
            async_stream(text_chunk("done")),
            cwd=str(tmp_path),
            tools=["read_file"],
        )

        with caplog.at_level(logging.WARNING):
            metadata = (await _collect(agent))[-1].metadata

        assert _warnings(caplog, _NO_USAGE) == [
            "backend reported no token usage across 3 turn(s); usage will not be recorded"
        ]
        assert metadata["usage"] == TokenUsage()

    @pytest.mark.asyncio
    async def test_profile_that_opts_out_is_not_warned_about_missing_usage(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        agent = _agent(async_stream(text_chunk("hi")), sends_stream_usage=False)

        with caplog.at_level(logging.WARNING):
            await _collect(agent)

        assert _warnings(caplog, _NO_USAGE) == []

    @pytest.mark.asyncio
    async def test_malformed_usage_on_two_turns_warns_once_per_field_per_call(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        (tmp_path / "a.txt").write_text("A")
        bad = {**_usage(5, 1), "prompt_tokens": "x", "completion_tokens": "y"}
        agent = _agent(
            async_stream(_read_call("c1"), usage_chunk(bad)),
            async_stream(text_chunk("done"), usage_chunk(bad)),
            async_stream(text_chunk("again"), usage_chunk(bad)),
            cwd=str(tmp_path),
            tools=["read_file"],
        )

        with caplog.at_level(logging.WARNING):
            await _collect(agent)
            first_call = len(_warnings(caplog, "malformed token usage"))
            await _collect(agent)

        assert first_call == 2
        assert len(_warnings(caplog, "malformed token usage")) == 4

    @pytest.mark.asyncio
    async def test_iteration_guard_exit_warns_with_turn_and_token_counts(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        (tmp_path / "a.txt").write_text("A")
        agent = _agent(
            async_stream(_read_call("c1"), usage_chunk(_usage(10, 1))),
            async_stream(_read_call("c2"), usage_chunk(_usage(20, 2))),
            cwd=str(tmp_path),
            tools=["read_file"],
            max_tool_iterations=2,
        )

        with caplog.at_level(logging.WARNING), pytest.raises(ProviderError):
            await _collect(agent)

        assert _warnings(caplog, _EXIT) == [
            "OpenAI agent ended without a final response after 2 turn(s) "
            "(prompt=30, cached=0, completion=3, reasoning=0 tokens)"
        ]

    @pytest.mark.asyncio
    async def test_normal_return_does_not_warn_exit(self, caplog: pytest.LogCaptureFixture) -> None:
        agent = _agent(async_stream(text_chunk("hi"), usage_chunk(_usage(5, 1))))

        with caplog.at_level(logging.WARNING):
            await _collect(agent)

        assert _warnings(caplog, _EXIT) == []


def _two_tool_turns() -> list[Any]:
    return [
        async_stream(_read_call("c1"), usage_chunk(_usage(10, 1, cached=2))),
        async_stream(_read_call("c2"), usage_chunk(_usage(20, 2, cached=4))),
    ]


class TestFailureTelemetry:
    @pytest.mark.asyncio
    async def test_request_failing_on_turn_three_carries_two_turns(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        (tmp_path / "a.txt").write_text("A")
        request = httpx.Request("POST", "http://test")
        rejected = openai.InternalServerError(
            "down", response=httpx.Response(503, request=request), body=None
        )
        agent = _agent(*_two_tool_turns(), rejected, cwd=str(tmp_path), tools=["read_file"])

        with caplog.at_level(logging.WARNING), pytest.raises(ProviderAPIError) as exc_info:
            await _collect(agent)

        telemetry = exc_info.value.telemetry
        assert telemetry is not None
        assert telemetry.turns == 2
        assert telemetry.usage == TokenUsage(prompt=30, cached=6, completion=3, reasoning=0)
        assert len(_warnings(caplog, _EXIT)) == 1

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("raised", "converted"),
        [
            (httpx.ReadTimeout("read timed out"), ProviderTimeoutError),
            (httpx.RemoteProtocolError("peer closed connection"), ProviderError),
        ],
        ids=["read-timeout", "remote-protocol"],
    )
    async def test_mid_stream_transport_failure_is_converted_with_telemetry(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
        raised: Exception,
        converted: type[ProviderError],
    ) -> None:
        (tmp_path / "a.txt").write_text("A")
        agent = _agent(
            *_two_tool_turns(),
            async_stream(text_chunk("partial"), raised),
            cwd=str(tmp_path),
            tools=["read_file"],
        )

        with caplog.at_level(logging.WARNING), pytest.raises(converted) as exc_info:
            await _collect(agent)

        assert exc_info.value.__cause__ is raised
        assert exc_info.value.telemetry is not None
        assert exc_info.value.telemetry.turns == 2
        assert _warnings(caplog, _EXIT) == [
            "OpenAI agent ended without a final response after 2 turn(s) "
            "(prompt=30, cached=6, completion=3, reasoning=0 tokens)"
        ]

    @pytest.mark.asyncio
    async def test_other_exception_propagates_unconverted_and_still_warns(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        (tmp_path / "a.txt").write_text("A")
        boom = RuntimeError("programming error")
        agent = _agent(
            _two_tool_turns()[0],
            async_stream(boom),
            cwd=str(tmp_path),
            tools=["read_file"],
        )

        with caplog.at_level(logging.WARNING), pytest.raises(RuntimeError) as exc_info:
            await _collect(agent)

        assert exc_info.value is boom
        assert _warnings(caplog, _EXIT) == [
            "OpenAI agent ended without a final response after 1 turn(s) "
            "(prompt=10, cached=2, completion=1, reasoning=0 tokens)"
        ]

    @pytest.mark.asyncio
    async def test_iteration_guard_error_carries_telemetry(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("A")
        agent = _agent(
            *_two_tool_turns(), cwd=str(tmp_path), tools=["read_file"], max_tool_iterations=2
        )

        with pytest.raises(ProviderError, match="max_tool_iterations") as exc_info:
            await _collect(agent)

        assert exc_info.value.telemetry is not None
        assert exc_info.value.telemetry.turns == 2

    @pytest.mark.asyncio
    async def test_empty_final_turn_keeps_turn_reasoning_and_carries_run_total(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "a.txt").write_text("A")
        agent = _agent(
            async_stream(_reasoning_chunk("abcd"), _read_call("c1"), usage_chunk(_usage(10, 1))),
            async_stream(_reasoning_chunk("ef"), usage_chunk(_usage(20, 2))),
            cwd=str(tmp_path),
            tools=["read_file"],
        )

        with pytest.raises(EmptyFinalTurnError) as exc_info:
            await _collect(agent)

        assert exc_info.value.reasoning_chars == 2
        telemetry = exc_info.value.telemetry
        assert telemetry is not None
        assert (telemetry.turns, telemetry.reasoning_chars) == (2, 6)
        assert telemetry.usage.prompt == 30


class TestReasoningEffort:
    """Slice 931 D3: reasoning_effort rides every request when set, and never otherwise."""

    @staticmethod
    def _sent(agent: OpenAICompatibleAgent) -> list[object]:
        client: Any = agent._client  # pyright: ignore[reportPrivateUsage]
        return [
            call.kwargs["reasoning_effort"] for call in client.chat.completions.create.call_args_list
        ]

    @pytest.mark.asyncio
    async def test_every_loop_turn_and_the_recovery_turn_carry_it(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("A")
        agent = _agent(
            async_stream(_read_call("c1")),
            async_stream(text_chunk("draft")),
            # A second handle_message on the same agent: the review's recovery turn.
            async_stream(text_chunk("review")),
            cwd=str(tmp_path),
            tools=["read_file"],
            effort=Effort.low,
        )

        await _collect(agent)
        await _collect(agent)

        assert self._sent(agent) == ["low", "low", "low"]

    @pytest.mark.asyncio
    async def test_none_is_sent_as_the_string_none(self) -> None:
        agent = _agent(async_stream(text_chunk("hi")), effort=Effort.none)

        await _collect(agent)

        assert self._sent(agent) == ["none"]

    @pytest.mark.asyncio
    async def test_unset_effort_is_omitted(self) -> None:
        from openai import omit

        agent = _agent(async_stream(text_chunk("hi")))

        await _collect(agent)

        assert self._sent(agent) == [omit]

    @pytest.mark.asyncio
    async def test_rejected_level_surfaces_as_provider_api_error(self) -> None:
        """D12 "backend rejects reasoning_effort": a 400 stays loud."""
        request = httpx.Request("POST", "http://test")
        rejected = openai.BadRequestError(
            "unsupported reasoning_effort", response=httpx.Response(400, request=request), body=None
        )
        agent = _agent(rejected, effort=Effort.xhigh)

        with pytest.raises(ProviderAPIError) as exc_info:
            await _collect(agent)

        assert exc_info.value.status_code == 400
        assert self._sent(agent) == ["xhigh"]
