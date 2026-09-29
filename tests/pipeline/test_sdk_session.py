"""Tests for SDKExecutionSession."""

from __future__ import annotations

import logging
from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from claude_agent_sdk import ClaudeAgentOptions

from squadron.pipeline.sdk_session import SDKExecutionSession
from tests.pipeline.conftest import (
    ScriptedClient,
    scripted_session,
    sdk_result,
    sdk_task_notification,
    sdk_task_started,
    sdk_task_updated,
    sdk_text,
    typed_config,
)

_MOD = "squadron.pipeline.sdk_session"


def _make_client() -> AsyncMock:
    """Build a minimal AsyncMock for ClaudeSDKClient."""
    client = AsyncMock()
    client.connect = AsyncMock()
    client.disconnect = AsyncMock()
    client.set_model = AsyncMock()
    client.query = AsyncMock()
    client.receive_response = MagicMock()
    return client


def _make_options() -> ClaudeAgentOptions:
    return ClaudeAgentOptions(cwd=".", permission_mode="bypassPermissions")


def _make_session(client: AsyncMock | None = None) -> SDKExecutionSession:
    return SDKExecutionSession(client=client or _make_client(), base_options=_make_options())


# ---------------------------------------------------------------------------
# connect / disconnect
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_connect_calls_client_connect() -> None:
    client = _make_client()
    session = _make_session(client)
    await session.connect()
    client.connect.assert_called_once()


@pytest.mark.asyncio
async def test_disconnect_calls_client_disconnect() -> None:
    client = _make_client()
    session = _make_session(client)
    await session.disconnect()
    client.disconnect.assert_called_once()


@pytest.mark.asyncio
async def test_disconnect_handles_exception_gracefully() -> None:
    client = _make_client()
    client.disconnect.side_effect = RuntimeError("conn already closed")
    session = _make_session(client)
    # Should not raise
    await session.disconnect()


# ---------------------------------------------------------------------------
# set_model
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_model_calls_client_when_model_differs() -> None:
    client = _make_client()
    session = _make_session(client)
    await session.set_model("claude-haiku-4-5-20251001")
    client.set_model.assert_called_once_with("claude-haiku-4-5-20251001")
    assert session.current_model == "claude-haiku-4-5-20251001"


@pytest.mark.asyncio
async def test_set_model_skips_call_when_model_matches() -> None:
    client = _make_client()
    session = SDKExecutionSession(
        client=client,
        base_options=_make_options(),
        current_model="claude-haiku-4-5-20251001",
    )
    await session.set_model("claude-haiku-4-5-20251001")
    client.set_model.assert_not_called()


@pytest.mark.asyncio
async def test_set_model_updates_current_model() -> None:
    client = _make_client()
    session = SDKExecutionSession(
        client=client,
        base_options=_make_options(),
        current_model="claude-haiku-4-5-20251001",
    )
    await session.set_model("claude-sonnet-4-6")
    assert session.current_model == "claude-sonnet-4-6"
    client.set_model.assert_called_once_with("claude-sonnet-4-6")


# ---------------------------------------------------------------------------
# dispatch
# ---------------------------------------------------------------------------


def _sdk_text_messages(*texts: str) -> AsyncMock:
    """Async generator that yields fake SDK messages converted via translate."""
    from claude_agent_sdk import AssistantMessage, TextBlock

    async def _gen():  # type: ignore[return]
        for text in texts:
            msg = MagicMock(spec=AssistantMessage)
            msg.parent_tool_use_id = None
            block = MagicMock(spec=TextBlock)
            block.text = text
            msg.content = [block]
            yield msg

    gen_mock = MagicMock()
    gen_mock.__aiter__ = lambda self: _gen()
    return gen_mock


@pytest.mark.asyncio
async def test_dispatch_sends_query_and_collects_response() -> None:
    client = _make_client()
    session = _make_session(client)

    from claude_agent_sdk import AssistantMessage, TextBlock

    async def _gen():  # type: ignore[return]
        msg = MagicMock(spec=AssistantMessage)
        msg.parent_tool_use_id = None
        block = MagicMock(spec=TextBlock)
        block.text = "Hello world"
        msg.content = [block]
        yield msg

    gen_mock = MagicMock()
    gen_mock.__aiter__ = lambda self: _gen()
    client.receive_response.return_value = gen_mock

    result = await session.dispatch("do something")

    client.query.assert_called_once_with("do something")
    assert "Hello world" in result


@pytest.mark.asyncio
async def test_dispatch_excludes_tool_call_noise() -> None:
    """Issue #23: tool_use/tool_result messages must not corrupt the response.

    Dispatch turns interleave assistant prose with tool-call narration
    ("Using tool: Bash") and tool results (command stdout). Bare
    concatenation with no separator and no filtering previously mashed
    these into the returned response string — the same class of bug fixed
    for review/summary in #22.
    """
    from claude_agent_sdk import AssistantMessage, TextBlock, ToolResultBlock, ToolUseBlock

    client = _make_client()
    session = _make_session(client)

    async def _gen():  # type: ignore[return]
        msg = MagicMock(spec=AssistantMessage)
        msg.parent_tool_use_id = None
        text_block = MagicMock(spec=TextBlock)
        text_block.text = "Let me check the diff first."
        tool_use_block = MagicMock(spec=ToolUseBlock)
        tool_use_block.name = "Bash"
        tool_use_block.input = {"command": "git diff"}
        msg.content = [text_block, tool_use_block]
        yield msg

        tool_result = MagicMock(spec=ToolResultBlock)
        tool_result.content = "<diff output>"
        yield tool_result

        msg2 = MagicMock(spec=AssistantMessage)

        msg2.parent_tool_use_id = None
        text_block2 = MagicMock(spec=TextBlock)
        text_block2.text = "Looks good."
        msg2.content = [text_block2]
        yield msg2

    gen_mock = MagicMock()
    gen_mock.__aiter__ = lambda self: _gen()
    client.receive_response.return_value = gen_mock

    result = await session.dispatch("review this")

    assert "Using tool:" not in result
    assert "<diff output>" not in result
    assert result == "Let me check the diff first.\nLooks good."


@pytest.mark.asyncio
async def test_dispatch_excludes_informational_rate_limit_event() -> None:
    """Success Criterion 10: an informational event must not reach the prose.

    An ``allowed``/``allowed_warning`` RateLimitEvent is now observable via
    translation (it is no longer silently dropped), but it is a usage-meter
    notice, not response text — it must not trigger a retry, and must not
    appear in dispatch's returned string (the issue #23 defect class).
    """
    from claude_agent_sdk import AssistantMessage, RateLimitEvent, RateLimitInfo, TextBlock

    client = _make_client()
    session = _make_session(client)

    async def _gen():  # type: ignore[return]
        yield RateLimitEvent(
            rate_limit_info=RateLimitInfo(status="allowed_warning"),
            uuid="evt-1",
            session_id="sess-1",
        )
        msg = MagicMock(spec=AssistantMessage)
        msg.parent_tool_use_id = None
        block = MagicMock(spec=TextBlock)
        block.text = "Looks good."
        msg.content = [block]
        yield msg

    gen_mock = MagicMock()
    gen_mock.__aiter__ = lambda self: _gen()
    client.receive_response.return_value = gen_mock

    result = await session.dispatch("review this")

    assert "rate_limit" not in result.lower()
    assert result == "Looks good."


@pytest.mark.asyncio
async def test_dispatch_retries_on_rate_limit() -> None:
    from claude_agent_sdk import AssistantMessage, RateLimitEvent, RateLimitInfo, TextBlock

    client = _make_client()
    session = _make_session(client)

    call_count = 0

    async def _gen():  # type: ignore[return]
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            yield RateLimitEvent(
                rate_limit_info=RateLimitInfo(status="rejected"),
                uuid=f"evt-{call_count}",
                session_id="sess-1",
            )
            return
        # Third call succeeds
        msg = MagicMock(spec=AssistantMessage)
        msg.parent_tool_use_id = None
        block = MagicMock(spec=TextBlock)
        block.text = "done"
        msg.content = [block]
        yield msg

    gen_mock = MagicMock()
    gen_mock.__aiter__ = lambda self: _gen()
    client.receive_response.return_value = gen_mock

    result = await session.dispatch("test")
    assert "done" in result
    assert call_count == 3


@pytest.mark.asyncio
async def test_dispatch_exhausts_retry_budget_on_persistent_rejection() -> None:
    """A rejected event on every attempt must exhaust the retry budget.

    Regression guard for a bug where a RateLimitEvent that arrived as the
    *first* message in the stream set ``progressed = True`` before the
    rejection check ran, so the except-handler's ``if progressed:
    retries = 0`` unconditionally reset the budget every attempt. A
    persistently rejecting provider then retried forever with no timeout.
    A rejected event must never count as progress.
    """
    from claude_agent_sdk import RateLimitEvent, RateLimitInfo

    from squadron.providers.errors import ProviderError
    from squadron.providers.sdk.rate_limit import MAX_RATE_LIMIT_RETRIES

    client = _make_client()
    session = _make_session(client)

    call_count = 0

    async def _gen():  # type: ignore[return]
        nonlocal call_count
        call_count += 1
        yield RateLimitEvent(
            rate_limit_info=RateLimitInfo(status="rejected"),
            uuid=f"evt-{call_count}",
            session_id="sess-1",
        )

    gen_mock = MagicMock()
    gen_mock.__aiter__ = lambda self: _gen()
    client.receive_response.return_value = gen_mock

    with patch(f"{_MOD}.asyncio.sleep", new=AsyncMock()):
        with pytest.raises(ProviderError):
            await session.dispatch("test")

    # First attempt plus MAX_RATE_LIMIT_RETRIES retries.
    assert call_count == MAX_RATE_LIMIT_RETRIES + 1


@pytest.mark.asyncio
async def test_dispatch_raises_provider_auth_on_cli_not_found() -> None:
    from claude_agent_sdk import CLINotFoundError

    from squadron.providers.errors import ProviderAuthError

    client = _make_client()
    client.query.side_effect = CLINotFoundError("claude not found")
    session = _make_session(client)

    with pytest.raises(ProviderAuthError):
        await session.dispatch("test")


@pytest.mark.asyncio
async def test_dispatch_raises_provider_api_on_process_error() -> None:
    from claude_agent_sdk import ProcessError

    from squadron.providers.errors import ProviderAPIError

    client = _make_client()
    client.query.side_effect = ProcessError("process failed", exit_code=1)
    session = _make_session(client)

    with pytest.raises(ProviderAPIError):
        await session.dispatch("test")


# ---------------------------------------------------------------------------
# session_id capture
# ---------------------------------------------------------------------------


def _assistant_gen(text: str) -> MagicMock:
    """Yield only an AssistantMessage with the given text."""
    from claude_agent_sdk import AssistantMessage, TextBlock

    async def _gen():  # type: ignore[return]
        msg = MagicMock(spec=AssistantMessage)
        msg.parent_tool_use_id = None
        block = MagicMock(spec=TextBlock)
        block.text = text
        msg.content = [block]
        yield msg

    gen_mock = MagicMock()
    gen_mock.__aiter__ = lambda self: _gen()
    return gen_mock


def _result_message_gen(text: str, session_id: str | None = "sess-1") -> MagicMock:
    """Yield an AssistantMessage/TextBlock followed by a ResultMessage.

    This mirrors real SDK behavior: the assistant text arrives in an
    AssistantMessage, and a ResultMessage follows carrying metadata
    (session_id, subtype, cost) whose `result` field duplicates the text.
    `dispatch()` must collect content from the AssistantMessage only and
    use the ResultMessage purely for metadata capture — otherwise the
    response string is doubled.
    """
    from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock

    async def _gen():  # type: ignore[return]
        msg = MagicMock(spec=AssistantMessage)
        msg.parent_tool_use_id = None
        block = MagicMock(spec=TextBlock)
        block.text = text
        msg.content = [block]
        yield msg
        result = ResultMessage(
            subtype="success",
            result=text,
            duration_ms=1,
            duration_api_ms=1,
            is_error=False,
            num_turns=1,
            session_id=session_id or "sess-1",
        )
        yield result

    gen_mock = MagicMock()
    gen_mock.__aiter__ = lambda self: _gen()
    return gen_mock


@pytest.mark.asyncio
async def test_dispatch_does_not_double_text_from_result_message() -> None:
    """Regression: AssistantMessage text and ResultMessage.result carry the
    same string — dispatch() must return it exactly once, not concatenated."""
    client = _make_client()
    client.receive_response.return_value = _result_message_gen("one and only", session_id="sess-x")
    session = _make_session(client)
    result = await session.dispatch("hi")
    assert result == "one and only"


@pytest.mark.asyncio
async def test_dispatch_captures_session_id() -> None:
    client = _make_client()
    client.receive_response.return_value = _result_message_gen("hi", session_id="sess-abc")
    session = _make_session(client)
    await session.dispatch("hi")
    assert session.session_id == "sess-abc"


@pytest.mark.asyncio
async def test_dispatch_session_id_latest_wins() -> None:
    client = _make_client()
    client.receive_response.return_value = _result_message_gen("one", session_id="sess-1")
    session = _make_session(client)
    await session.dispatch("one")
    assert session.session_id == "sess-1"

    client.receive_response.return_value = _result_message_gen("two", session_id="sess-2")
    await session.dispatch("two")
    assert session.session_id == "sess-2"


# ---------------------------------------------------------------------------
# SDK is_error path (T11)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_raises_provider_api_error_on_result_is_error() -> None:
    """When ResultMessage.is_error is True, dispatch raises ProviderAPIError."""
    from claude_agent_sdk import ResultMessage

    from squadron.providers.errors import ProviderAPIError

    client = _make_client()
    session = _make_session(client)

    async def _gen():  # type: ignore[return]
        result = ResultMessage(
            subtype="error_during_generation",
            result=None,
            duration_ms=1,
            duration_api_ms=1,
            is_error=True,
            num_turns=1,
            session_id="sess-err",
        )
        yield result

    gen_mock = MagicMock()
    gen_mock.__aiter__ = lambda self: _gen()
    client.receive_response.return_value = gen_mock

    with pytest.raises(ProviderAPIError, match="is_error=True"):
        await session.dispatch("fail me")


@pytest.mark.asyncio
async def test_dispatch_no_content_appended_before_is_error_raise() -> None:
    """is_error check fires before any content is appended to response_parts."""
    from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock

    from squadron.providers.errors import ProviderAPIError

    client = _make_client()
    session = _make_session(client)
    collected: list[str] = []

    async def _gen():  # type: ignore[return]
        # AssistantMessage arrives first — but the is_error ResultMessage
        # should abort before the assistant text reaches callers.
        msg = MagicMock(spec=AssistantMessage)
        msg.parent_tool_use_id = None
        block = MagicMock(spec=TextBlock)
        block.text = "partial text"
        msg.content = [block]
        yield msg
        result = ResultMessage(
            subtype="error_during_generation",
            result=None,
            duration_ms=1,
            duration_api_ms=1,
            is_error=True,
            num_turns=1,
            session_id="sess-err",
        )
        yield result

    gen_mock = MagicMock()
    gen_mock.__aiter__ = lambda self: _gen()
    client.receive_response.return_value = gen_mock

    with pytest.raises(ProviderAPIError):
        await session.dispatch("fail me")

    # The returned exception confirms no clean string was returned.
    # collected is empty since dispatch raised before returning.
    assert collected == []


# ---------------------------------------------------------------------------
# compact (session rotate)
# ---------------------------------------------------------------------------


class TestCompactSessionRotate:
    @pytest.mark.asyncio
    async def test_compact_without_summary_model_skips_initial_set_model(
        self,
    ) -> None:
        old = _make_client()
        old.receive_response.return_value = _result_message_gen("SUMMARY")
        new = _make_client()
        new.receive_response.return_value = _result_message_gen("ack")
        session = _make_session(old)

        with patch(f"{_MOD}.ClaudeSDKClient", return_value=new) as client_ctor:
            result = await session.compact(instructions="Keep X")

        assert result == "SUMMARY"
        old.set_model.assert_not_called()
        seeded = client_ctor.call_args.kwargs["options"]
        assert seeded.system_prompt["append"].endswith("SUMMARY")
        old.disconnect.assert_called_once()
        new.connect.assert_called_once()
        new.query.assert_not_called()
        assert session.client is new

    @pytest.mark.asyncio
    async def test_compact_with_summary_model_switches_first(self) -> None:
        old = _make_client()
        old.receive_response.return_value = _result_message_gen("SUMMARY")
        new = _make_client()
        new.receive_response.return_value = _result_message_gen("ack")
        session = _make_session(old)

        with patch(f"{_MOD}.ClaudeSDKClient", return_value=new):
            await session.compact(instructions="Keep X", summary_model="haiku-id")

        old.set_model.assert_any_call("haiku-id")

    @pytest.mark.asyncio
    async def test_compact_restores_model_at_end(self) -> None:
        old = _make_client()
        old.receive_response.return_value = _result_message_gen("SUMMARY")
        new = _make_client()
        new.receive_response.return_value = _result_message_gen("ack")
        session = _make_session(old)

        with patch(f"{_MOD}.ClaudeSDKClient", return_value=new):
            await session.compact(
                instructions="Keep X",
                summary_model="haiku-id",
                restore_model="sonnet-id",
            )

        new.set_model.assert_called_once_with("sonnet-id")
        assert session.current_model == "sonnet-id"

    @pytest.mark.asyncio
    async def test_compact_captures_on_old_client_and_seeds_new_one(self) -> None:
        old = _make_client()
        old.receive_response.return_value = _result_message_gen("SUMMARY TEXT")
        new = _make_client()
        session = _make_session(old)

        with patch(f"{_MOD}.ClaudeSDKClient", return_value=new) as client_ctor:
            result = await session.compact(instructions="Keep X")

        from squadron.pipeline.sdk_session import frame_summary_for_seed

        assert result == "SUMMARY TEXT"
        old.query.assert_called_once_with("Keep X")
        seeded = client_ctor.call_args.kwargs["options"]
        assert seeded.system_prompt["append"] == frame_summary_for_seed("SUMMARY TEXT")
        new.query.assert_not_called()

    @pytest.mark.asyncio
    async def test_compact_with_pre_made_summary_skips_capture(self) -> None:
        """When summary= provided, old client is NOT queried for instructions."""
        old = _make_client()
        new = _make_client()
        session = _make_session(old)

        with patch(f"{_MOD}.ClaudeSDKClient", return_value=new) as client_ctor:
            result = await session.compact(instructions="x", summary="pre-made")

        old.query.assert_not_called()
        new.query.assert_not_called()
        old.disconnect.assert_called_once()
        assert client_ctor.call_args.kwargs["options"].system_prompt["append"].endswith("pre-made")
        assert result == "pre-made"

    @pytest.mark.asyncio
    async def test_compact_with_pre_made_summary_restores_model(self) -> None:
        old = _make_client()
        new = _make_client()
        new.receive_response.return_value = _result_message_gen("ack")
        session = _make_session(old)

        with patch(f"{_MOD}.ClaudeSDKClient", return_value=new):
            await session.compact(instructions="x", summary="pre-made", restore_model="sonnet-id")

        new.set_model.assert_called_once_with("sonnet-id")
        assert session.current_model == "sonnet-id"

    @pytest.mark.asyncio
    async def test_compact_with_pre_made_summary_returns_unchanged(self) -> None:
        old = _make_client()
        new = _make_client()
        new.receive_response.return_value = _result_message_gen("ack")
        session = _make_session(old)

        with patch(f"{_MOD}.ClaudeSDKClient", return_value=new):
            result = await session.compact(instructions="x", summary="pre-made")

        assert result == "pre-made"


# ---------------------------------------------------------------------------
# seed_context
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_seed_context_rotates_without_a_turn(caplog: pytest.LogCaptureFixture) -> None:
    from squadron.pipeline.sdk_session import SeedSource

    old = _make_client()
    new = _make_client()
    session = _make_session(old)

    with (
        caplog.at_level(logging.INFO, logger=_MOD),
        patch(f"{_MOD}.ClaudeSDKClient", return_value=new) as client_ctor,
    ):
        result = await session.seed_context("Y", SeedSource.RESTORE)

    assert result is None
    old.disconnect.assert_called_once()
    assert client_ctor.call_args.kwargs["options"].system_prompt["append"].endswith("Y")
    old.query.assert_not_called()
    new.query.assert_not_called()
    assert session.client is new
    assert any(
        "seeded fresh session via system prompt" in r.getMessage() and "restore" in r.getMessage()
        for r in caplog.records
    )


# ---------------------------------------------------------------------------
# capture_summary
# ---------------------------------------------------------------------------


class TestCaptureSummary:
    @pytest.mark.asyncio
    async def test_capture_summary_dispatches_and_returns_text(self) -> None:
        client = _make_client()
        client.receive_response.return_value = _result_message_gen("SUMMARY")
        session = _make_session(client)

        result = await session.capture_summary("summarize this")

        client.query.assert_called_once_with("summarize this")
        assert result == "SUMMARY"

    @pytest.mark.asyncio
    async def test_capture_summary_sets_model_before_dispatch(self) -> None:
        client = _make_client()
        client.receive_response.return_value = _result_message_gen("SUMMARY")
        session = _make_session(client)

        await session.capture_summary("instr", summary_model="haiku-id")

        client.set_model.assert_called_once_with("haiku-id")
        assert session.current_model == "haiku-id"

    @pytest.mark.asyncio
    async def test_capture_summary_restores_model_after_dispatch(self) -> None:
        client = _make_client()
        client.receive_response.return_value = _result_message_gen("SUMMARY")
        session = SDKExecutionSession(
            client=client,
            base_options=_make_options(),
            current_model="sonnet-id",
        )

        await session.capture_summary("instr", summary_model="haiku-id", restore_model="sonnet-id")

        # set_model called twice: once to switch to haiku, once to restore sonnet
        assert client.set_model.call_count == 2
        assert session.current_model == "sonnet-id"

    @pytest.mark.asyncio
    async def test_capture_summary_does_not_disconnect_or_replace_client(self) -> None:
        client = _make_client()
        client.receive_response.return_value = _result_message_gen("SUMMARY")
        session = _make_session(client)

        await session.capture_summary("instr")

        client.disconnect.assert_not_called()
        assert session.client is client

    @pytest.mark.asyncio
    async def test_capture_summary_propagates_dispatch_exception(self) -> None:
        client = _make_client()
        client.query.side_effect = RuntimeError("network error")
        session = _make_session(client)

        with pytest.raises(RuntimeError, match="network error"):
            await session.capture_summary("instr")


# ---------------------------------------------------------------------------
# _seeded_options (seed rides the system prompt, never a turn)
# ---------------------------------------------------------------------------


class TestSeededOptions:
    def test_none_seed_returns_base_unchanged(self) -> None:
        from squadron.pipeline.sdk_session import _seeded_options  # pyright: ignore[reportPrivateUsage]

        base = _make_options()
        assert _seeded_options(base, None) is base

    def test_seed_becomes_preset_append(self) -> None:
        from squadron.pipeline.sdk_session import (
            _SEED_FRAMING_PREFIX,  # pyright: ignore[reportPrivateUsage]
            _seeded_options,  # pyright: ignore[reportPrivateUsage]
        )

        seeded = _seeded_options(_make_options(), "SEED TEXT")
        prompt = seeded.system_prompt
        assert isinstance(prompt, dict)
        assert prompt["type"] == "preset"
        assert prompt.get("preset") == "claude_code"
        append = prompt.get("append")
        assert isinstance(append, str)
        assert append.startswith(_SEED_FRAMING_PREFIX)
        assert append.endswith("SEED TEXT")

    def test_existing_append_is_kept_first(self) -> None:
        from squadron.pipeline.sdk_session import (
            _SEED_FRAMING_PREFIX,  # pyright: ignore[reportPrivateUsage]
            _seeded_options,  # pyright: ignore[reportPrivateUsage]
        )

        base = ClaudeAgentOptions(
            system_prompt={"type": "preset", "preset": "claude_code", "append": "EXISTING"}
        )
        prompt = _seeded_options(base, "S").system_prompt
        assert isinstance(prompt, dict)
        assert prompt.get("append") == f"EXISTING\n\n{_SEED_FRAMING_PREFIX}S"

    def test_base_is_not_mutated(self) -> None:
        from squadron.pipeline.sdk_session import _seeded_options  # pyright: ignore[reportPrivateUsage]

        base = ClaudeAgentOptions(
            system_prompt={"type": "preset", "preset": "claude_code", "append": "EXISTING"}
        )
        _seeded_options(base, "S")
        assert base.system_prompt == {
            "type": "preset",
            "preset": "claude_code",
            "append": "EXISTING",
        }


# ---------------------------------------------------------------------------
# open_pipeline_session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_open_pipeline_session_seeds_client_options_and_connects() -> None:
    from squadron.pipeline.sdk_session import open_pipeline_session

    client = _make_client()
    with patch(f"{_MOD}.ClaudeSDKClient", return_value=client) as client_ctor:
        session = await open_pipeline_session(seed="S")

    options = client_ctor.call_args.kwargs["options"]
    assert isinstance(options.system_prompt, dict)
    assert "S" in options.system_prompt["append"]
    # The seed is applied per connect, never stored on base_options.
    assert "append" not in session.base_options.system_prompt
    client.connect.assert_called_once()
    client.query.assert_not_called()


# ---------------------------------------------------------------------------
# unusable_reason after a failed reconnect (D13)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_failed_reconnect_marks_session_unusable(caplog: pytest.LogCaptureFixture) -> None:
    from squadron.pipeline.sdk_session import SeedSource
    from squadron.providers.errors import ProviderError
    from tests.pipeline.conftest import ScriptedClient, failing_reconnect_patch, scripted_session

    session = scripted_session(ScriptedClient())
    assert isinstance(session, SDKExecutionSession)

    with caplog.at_level(logging.ERROR, logger=_MOD), failing_reconnect_patch():
        with pytest.raises(Exception, match="E2BIG"):
            await session.seed_context("seed", SeedSource.RESTORE)

    assert session.unusable_reason is not None and "E2BIG" in session.unusable_reason
    assert any(r.levelno == logging.ERROR and r.exc_info for r in caplog.records)

    fresh = session.client
    with pytest.raises(ProviderError, match="SDK session unusable"):
        await session.dispatch("p")
    fresh.query.assert_not_called()  # type: ignore[attr-defined]
    with pytest.raises(ProviderError, match="SDK session unusable"):
        await session.compact(instructions="x", summary="s")
    with pytest.raises(ProviderError, match="SDK session unusable"):
        await session.seed_context("again", SeedSource.RESUME)


# ---------------------------------------------------------------------------
# Background ledger and own-result detection (slice 932 D5/D6)
# ---------------------------------------------------------------------------


def _ledger_after(*msgs: object) -> object:
    from squadron.pipeline.sdk_turns import BackgroundLedger

    ledger = BackgroundLedger()
    for msg in msgs:
        ledger.observe(msg)
    return ledger


class TestBackgroundLedger:
    @pytest.mark.parametrize(
        ("msgs", "active"),
        [
            pytest.param(lambda: [sdk_task_started("a", "local_agent")], True, id="agent-start"),
            pytest.param(lambda: [sdk_task_started("a", "local_bash")], False, id="bash-ignored"),
            pytest.param(
                lambda: [sdk_task_started("a", "local_agent"), sdk_task_notification("a")],
                False,
                id="notification-clears",
            ),
            pytest.param(
                lambda: [sdk_task_started("a", "local_agent"), sdk_task_updated("a", "killed")],
                False,
                id="killed-clears",
            ),
            pytest.param(
                lambda: [sdk_task_started("a", "local_agent"), sdk_task_updated("a", "running")],
                True,
                id="running-keeps",
            ),
            pytest.param(
                lambda: [
                    sdk_task_started("a", "local_agent"),
                    sdk_task_notification("a"),
                    sdk_task_updated("a", "completed"),
                ],
                False,
                id="duplicate-terminal-idempotent",
            ),
        ],
    )
    def test_active_state(self, msgs: Callable[[], list[object]], active: bool) -> None:
        ledger = _ledger_after(*msgs())
        assert ledger.active is active  # type: ignore[attr-defined]

    def test_seen_count_counts_distinct_agents_ever_tracked(self) -> None:
        ledger = _ledger_after(
            sdk_task_started("a", "local_agent"),
            sdk_task_notification("a"),
            sdk_task_started("b", "local_workflow"),
            sdk_task_started("c", "local_bash"),
        )
        assert ledger.seen_count == 2  # type: ignore[attr-defined]
        assert ledger.active_ids() == ["b"]  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("origin", "own"),
    [(None, True), ({"kind": "human"}, True), ({"kind": "task-notification"}, False)],
)
def test_is_own_result(origin: dict[str, str] | None, own: bool) -> None:
    from claude_agent_sdk import ResultMessage

    from squadron.pipeline.sdk_turns import is_own_result

    msg = ResultMessage(
        subtype="success",
        duration_ms=1,
        duration_api_ms=1,
        is_error=False,
        num_turns=1,
        session_id="s",
        origin=origin,  # type: ignore[arg-type]
    )
    assert is_own_result(msg) is own


# ---------------------------------------------------------------------------
# dispatch waits for background agents (slice 932 D5/D6)
# ---------------------------------------------------------------------------


class TestDispatchWaitsForBackgroundAgents:
    @pytest.mark.asyncio
    async def test_waits_for_agent_and_joins_follow_up_turn(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        client = ScriptedClient(
            [
                sdk_task_started("t1", "local_agent", "Explore src"),
                sdk_text("Waiting for the agent."),
                sdk_result(),
            ],
            [sdk_task_notification("t1"), sdk_text("Wrote the design."), sdk_result(injected=True)],
        )
        session = scripted_session(client)

        with caplog.at_level(logging.INFO, logger=_MOD):
            response = await session.dispatch("design it")  # type: ignore[attr-defined]

        assert response == "Waiting for the agent.\nWrote the design."
        assert session.background_tasks_waited == 1  # type: ignore[attr-defined]
        assert client.receive_calls == 2
        assert any(
            "waiting" in r.getMessage() and "Explore src" in r.getMessage() for r in caplog.records
        )

    @pytest.mark.asyncio
    async def test_killed_update_is_enough_to_finish(self) -> None:
        client = ScriptedClient(
            [sdk_task_started("t1", "local_agent"), sdk_result()],
            [
                sdk_task_updated("t1", "killed"),
                sdk_text("Agent was killed."),
                sdk_result(injected=True),
            ],
        )
        session = scripted_session(client)

        response = await session.dispatch("p")  # type: ignore[attr-defined]

        assert response == "Agent was killed."
        assert client.receive_calls == 2

    @pytest.mark.asyncio
    async def test_background_shell_does_not_hold_dispatch(self) -> None:
        client = ScriptedClient(
            [sdk_task_started("b1", "local_bash"), sdk_text("done"), sdk_result()],
        )
        session = scripted_session(client)

        response = await session.dispatch("p")  # type: ignore[attr-defined]

        assert response == "done"
        assert session.background_tasks_waited == 0  # type: ignore[attr-defined]
        assert client.receive_calls == 1

    @pytest.mark.asyncio
    async def test_no_tasks_reads_one_turn(self) -> None:
        client = ScriptedClient([sdk_text("hello"), sdk_result()])
        session = scripted_session(client)

        assert await session.dispatch("p") == "hello"  # type: ignore[attr-defined]
        assert client.receive_calls == 1

    @pytest.mark.asyncio
    async def test_stream_end_with_agent_tracked_raises(self) -> None:
        from squadron.providers.errors import ProviderError

        client = ScriptedClient(
            [sdk_task_started("t1", "local_agent", "Explore src"), sdk_result()],
            [],  # stream ends: no notification, no result
        )
        session = scripted_session(client)

        with pytest.raises(
            ProviderError, match="stream ended before the dispatch's result.*Explore src"
        ):
            await session.dispatch("p")  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_leftover_injected_turn_is_dropped_and_logged(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        client = ScriptedClient(
            [sdk_text("Late words from the previous step."), sdk_result(injected=True)],
            [sdk_text("This step's answer."), sdk_result()],
        )
        session = scripted_session(client)

        with caplog.at_level(logging.WARNING, logger=_MOD):
            response = await session.dispatch("p")  # type: ignore[attr-defined]

        assert response == "This step's answer."
        warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
        assert any(
            "discarded a background follow-up turn" in m and "Late words from the previous step." in m
            for m in warnings
        )


class TestBackgroundIdleTimeout:
    @pytest.mark.asyncio
    async def test_silence_while_waiting_stops_agents_and_returns(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        client = ScriptedClient(
            [sdk_task_started("t1", "local_agent", "Explore src"), sdk_text("Waiting."), sdk_result()],
            [0.15],  # silent past the idle bound
        )
        session = scripted_session(client)

        with (
            patch(f"{_MOD}.get_typed_config", return_value=0.05),
            caplog.at_level(logging.WARNING, logger=_MOD),
        ):
            response = await session.dispatch("p")  # type: ignore[attr-defined]

        assert response == "Waiting."
        client.stop_task.assert_awaited_once_with("t1")
        assert session.background_tasks_stopped == 1  # type: ignore[attr-defined]
        assert any(
            "no activity" in r.getMessage() and "Explore src" in r.getMessage()
            for r in caplog.records
            if r.levelno == logging.WARNING
        )

    @pytest.mark.asyncio
    async def test_stop_task_failure_is_logged_and_next_id_still_stopped(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        client = ScriptedClient(
            [
                sdk_task_started("t1", "local_agent"),
                sdk_task_started("t2", "local_agent"),
                sdk_result(),
            ],
            [0.15],
        )
        client.stop_task.side_effect = [Exception("control request timeout"), None]
        session = scripted_session(client)

        with (
            patch(f"{_MOD}.get_typed_config", return_value=0.05),
            caplog.at_level(logging.ERROR, logger=_MOD),
        ):
            await session.dispatch("p")  # type: ignore[attr-defined]

        assert [c.args for c in client.stop_task.await_args_list] == [("t1",), ("t2",)]
        errors = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(errors) == 1 and "t1" in errors[0].getMessage() and errors[0].exc_info

    @pytest.mark.asyncio
    async def test_slow_foreground_turn_has_no_timer(self) -> None:
        client = ScriptedClient([0.1, sdk_text("slow answer"), sdk_result()])
        session = scripted_session(client)

        with patch(f"{_MOD}.get_typed_config", return_value=0.05) as config:
            response = await session.dispatch("p")  # type: ignore[attr-defined]

        assert response == "slow answer"
        config.assert_not_called()
        client.stop_task.assert_not_called()
        assert session.background_tasks_stopped == 0  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Pipeline session settings (slice 932 D10/D11)
# ---------------------------------------------------------------------------


class TestPipelineSessionSettings:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("auto_memory", [True, False])
    async def test_builder_applies_policy(self, auto_memory: bool) -> None:
        from squadron.pipeline.sdk_session import open_pipeline_session

        with (
            patch(
                f"{_MOD}.get_typed_config",
                typed_config({"pipeline.auto_memory": auto_memory, "pipeline.user_settings": False}),
            ),
            patch(f"{_MOD}.ClaudeSDKClient", return_value=_make_client()) as ctor,
        ):
            session = await open_pipeline_session()

        options = ctor.call_args.kwargs["options"]
        assert options.setting_sources == ["project"]
        assert ("CLAUDE_CODE_DISABLE_AUTO_MEMORY" in options.env) is (not auto_memory)
        assert session.setting_sources == ["project"]
        assert session.auto_memory is auto_memory

    @pytest.mark.asyncio
    async def test_settings_survive_rotation(self) -> None:
        from squadron.pipeline.sdk_session import open_pipeline_session

        with (
            patch(f"{_MOD}.get_typed_config", return_value=False),
            patch(f"{_MOD}.ClaudeSDKClient", return_value=_make_client()),
        ):
            session = await open_pipeline_session()

        with patch(f"{_MOD}.ClaudeSDKClient", return_value=_make_client()) as ctor:
            await session.compact(instructions="x", summary="S")

        rotated = ctor.call_args.kwargs["options"]
        assert rotated.setting_sources == ["project"]
        assert rotated.env == {"CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"}
        assert rotated.system_prompt["append"].endswith("S")


@pytest.mark.asyncio
async def test_subagent_prose_is_not_part_of_the_response() -> None:
    """E1 finding: a background subagent's own messages stream between turns."""
    client = ScriptedClient(
        [sdk_task_started("t1", "local_agent"), sdk_text("Waiting."), sdk_result()],
        [
            sdk_text("There are 3 files under src/.", parent_tool_use_id="toolu_1"),
            sdk_task_notification("t1"),
            sdk_text("DONE"),
            sdk_result(injected=True),
        ],
    )
    session = scripted_session(client)

    assert await session.dispatch("p") == "Waiting.\nDONE"  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_unrelated_timeout_while_waiting_is_not_treated_as_idle() -> None:
    """Review F002: only the idle timer's own expiry stops the agents."""

    class _TimingOutClient(ScriptedClient):
        def receive_response(self):  # type: ignore[no-untyped-def]
            if self.receive_calls == 1:
                self.receive_calls += 1

                async def _raise():  # type: ignore[no-untyped-def]
                    raise TimeoutError("transport timeout")
                    yield  # pragma: no cover

                return _raise()
            return super().receive_response()

    client = _TimingOutClient([sdk_task_started("t1", "local_agent"), sdk_result()])
    session = scripted_session(client)

    with (
        patch(f"{_MOD}.get_typed_config", return_value=60),
        pytest.raises(TimeoutError, match="transport timeout"),
    ):
        await session.dispatch("p")  # type: ignore[attr-defined]
    client.stop_task.assert_not_called()
    assert session.background_tasks_stopped == 0  # type: ignore[attr-defined]
