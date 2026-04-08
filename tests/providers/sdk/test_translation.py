"""Tests for SDK message → squadron Message translation."""

from __future__ import annotations

import pytest
from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
)

from squadron.core.models import Message, MessageType
from squadron.providers.sdk.translation import translate_sdk_message

SENDER = "test-agent"


# ---------------------------------------------------------------------------
# AssistantMessage with TextBlock
# ---------------------------------------------------------------------------


class TestAssistantTextBlock:
    def test_single_text_block(self) -> None:
        sdk_msg = AssistantMessage(
            content=[TextBlock(text="Hello world")],
            model="claude-sonnet-4-20250514",
        )
        result = translate_sdk_message(sdk_msg, sender=SENDER)
        assert len(result) == 1
        msg = result[0]
        assert isinstance(msg, Message)
        assert msg.content == "Hello world"
        assert msg.message_type == MessageType.chat
        assert msg.metadata["sdk_type"] == "assistant_text"

    def test_sender_and_recipients(self) -> None:
        sdk_msg = AssistantMessage(
            content=[TextBlock(text="hi")],
            model="claude-sonnet-4-20250514",
        )
        result = translate_sdk_message(sdk_msg, sender=SENDER)
        assert result[0].sender == SENDER
        assert result[0].recipients == ["all"]


# ---------------------------------------------------------------------------
# AssistantMessage with ToolUseBlock
# ---------------------------------------------------------------------------


class TestAssistantToolUseBlock:
    def test_single_tool_use_block(self) -> None:
        sdk_msg = AssistantMessage(
            content=[
                ToolUseBlock(
                    id="tu-1",
                    name="read_file",
                    input={"path": "/tmp/a.py"},
                ),
            ],
            model="claude-sonnet-4-20250514",
        )
        result = translate_sdk_message(sdk_msg, sender=SENDER)
        assert len(result) == 1
        msg = result[0]
        assert msg.content == "Using tool: read_file"
        assert msg.message_type == MessageType.system
        assert msg.metadata["sdk_type"] == "tool_use"
        assert msg.metadata["tool_name"] == "read_file"
        assert msg.metadata["tool_input"] == {"path": "/tmp/a.py"}


# ---------------------------------------------------------------------------
# AssistantMessage with mixed blocks
# ---------------------------------------------------------------------------


class TestAssistantMixedBlocks:
    def test_text_tooluse_text(self) -> None:
        sdk_msg = AssistantMessage(
            content=[
                TextBlock(text="Let me read the file."),
                ToolUseBlock(id="tu-2", name="bash", input={"cmd": "ls"}),
                TextBlock(text="Here are the results."),
            ],
            model="claude-sonnet-4-20250514",
        )
        result = translate_sdk_message(sdk_msg, sender=SENDER)
        assert len(result) == 3
        assert result[0].message_type == MessageType.chat
        assert result[1].message_type == MessageType.system
        assert result[2].message_type == MessageType.chat
        assert result[0].content == "Let me read the file."
        assert result[1].metadata["tool_name"] == "bash"
        assert result[2].content == "Here are the results."

    def test_empty_content_list(self) -> None:
        sdk_msg = AssistantMessage(content=[], model="claude-sonnet-4-20250514")
        result = translate_sdk_message(sdk_msg, sender=SENDER)
        assert result == []


# ---------------------------------------------------------------------------
# ToolResultBlock
# ---------------------------------------------------------------------------


class TestToolResultBlock:
    def test_string_content(self) -> None:
        block = ToolResultBlock(tool_use_id="tu-1", content="file contents here")
        result = translate_sdk_message(block, sender=SENDER)
        assert len(result) == 1
        msg = result[0]
        assert msg.content == "file contents here"
        assert msg.message_type == MessageType.system
        assert msg.metadata["sdk_type"] == "tool_result"

    def test_list_content_coerced_to_str(self) -> None:
        block = ToolResultBlock(
            tool_use_id="tu-1",
            content=[{"type": "text", "text": "output"}],
        )
        result = translate_sdk_message(block, sender=SENDER)
        assert len(result) == 1
        assert isinstance(result[0].content, str)

    def test_none_content(self) -> None:
        block = ToolResultBlock(tool_use_id="tu-1", content=None)
        result = translate_sdk_message(block, sender=SENDER)
        assert len(result) == 1
        assert result[0].content == "None"


# ---------------------------------------------------------------------------
# ResultMessage
# ---------------------------------------------------------------------------


class TestResultMessage:
    @pytest.fixture
    def _base_kwargs(self) -> dict:
        return {
            "duration_ms": 1000,
            "duration_api_ms": 800,
            "is_error": False,
            "num_turns": 1,
            "session_id": "sess-1",
        }

    def test_success_subtype(self, _base_kwargs: dict) -> None:
        msg = ResultMessage(
            subtype="success",
            result="Task completed.",
            **_base_kwargs,
        )
        result = translate_sdk_message(msg, sender=SENDER)
        assert len(result) == 1
        assert result[0].content == "Task completed."
        assert result[0].message_type == MessageType.chat
        assert result[0].metadata["sdk_type"] == "result"
        assert result[0].metadata["subtype"] == "success"

    def test_success_captures_session_id(self) -> None:
        msg = ResultMessage(
            subtype="success",
            result="ok",
            duration_ms=1,
            duration_api_ms=1,
            is_error=False,
            num_turns=1,
            session_id="sess-abc",
        )
        result = translate_sdk_message(msg, sender=SENDER)
        assert result[0].metadata["session_id"] == "sess-abc"

    def test_error_subtype(self, _base_kwargs: dict) -> None:
        msg = ResultMessage(
            subtype="error",
            result="Something went wrong",
            is_error=True,
            duration_ms=500,
            duration_api_ms=400,
            num_turns=0,
            session_id="sess-2",
        )
        result = translate_sdk_message(msg, sender=SENDER)
        assert len(result) == 1
        assert result[0].message_type == MessageType.system
        assert result[0].metadata["subtype"] == "error"

    def test_error_captures_session_id(self) -> None:
        msg = ResultMessage(
            subtype="error",
            result="boom",
            duration_ms=1,
            duration_api_ms=1,
            is_error=True,
            num_turns=0,
            session_id="sess-err",
        )
        result = translate_sdk_message(msg, sender=SENDER)
        assert result[0].metadata["session_id"] == "sess-err"

    def test_no_result_attribute(self, _base_kwargs: dict) -> None:
        msg = ResultMessage(subtype="success", **_base_kwargs)
        result = translate_sdk_message(msg, sender=SENDER)
        assert len(result) == 1
        # Falls back to str(msg) since result is None
        assert isinstance(result[0].content, str)
        assert len(result[0].content) > 0


# ---------------------------------------------------------------------------
# Unknown types
# ---------------------------------------------------------------------------


class TestUnknownTypes:
    def test_plain_string(self) -> None:
        result = translate_sdk_message("some string", sender=SENDER)
        assert result == []

    def test_plain_object(self) -> None:
        result = translate_sdk_message(object(), sender=SENDER)
        assert result == []

    def test_none(self) -> None:
        result = translate_sdk_message(None, sender=SENDER)
        assert result == []


# ---------------------------------------------------------------------------
# Message validity
# ---------------------------------------------------------------------------


class TestMessageValidity:
    def test_messages_have_uuid_ids(self) -> None:
        sdk_msg = AssistantMessage(
            content=[TextBlock(text="test")],
            model="claude-sonnet-4-20250514",
        )
        result = translate_sdk_message(sdk_msg, sender=SENDER)
        assert result[0].id  # non-empty
        # Should be valid UUID format
        assert len(result[0].id) == 36

    def test_messages_have_timestamps(self) -> None:
        sdk_msg = AssistantMessage(
            content=[TextBlock(text="test")],
            model="claude-sonnet-4-20250514",
        )
        result = translate_sdk_message(sdk_msg, sender=SENDER)
        assert result[0].timestamp is not None
