"""Tests for providers/openai/translation.py."""

from __future__ import annotations

from squadron.core.models import MessageType
from squadron.providers.openai.translation import (
    build_assistant_history_entry,
    build_messages,
    build_text_message,
    build_tool_call_message,
    build_tool_result_entry,
    build_tool_schemas,
)
from squadron.tools import ToolDescriptor, ToolResult

_AGENT = "test-agent"
_MODEL = "gpt-4o-mini"


class TestBuildTextMessage:
    def test_non_empty_returns_chat_message(self) -> None:
        msg = build_text_message("Hello", _AGENT, _MODEL)
        assert msg is not None
        assert msg.content == "Hello"
        assert msg.sender == _AGENT
        assert msg.recipients == ["all"]
        assert msg.message_type == MessageType.chat
        assert msg.metadata["provider"] == "openai"
        assert msg.metadata["model"] == _MODEL

    def test_empty_string_returns_none(self) -> None:
        assert build_text_message("", _AGENT, _MODEL) is None

    def test_whitespace_only_returns_none(self) -> None:
        assert build_text_message("   ", _AGENT, _MODEL) is None


class TestBuildToolCallMessage:
    def test_metadata_fields_present(self) -> None:
        tc = {
            "id": "call_abc",
            "function": {"name": "my_tool", "arguments": '{"x": 1}'},
        }
        msg = build_tool_call_message(tc, _AGENT)
        assert msg.message_type == MessageType.system
        assert msg.metadata["provider"] == "openai"
        assert msg.metadata["type"] == "tool_call"
        assert msg.metadata["tool_call_id"] == "call_abc"
        assert msg.metadata["tool_name"] == "my_tool"
        assert msg.metadata["tool_arguments"] == '{"x": 1}'

    def test_content_contains_tool_name(self) -> None:
        tc = {"id": "c1", "function": {"name": "search", "arguments": "{}"}}
        msg = build_tool_call_message(tc, _AGENT)
        assert "search" in msg.content


class TestBuildMessages:
    def test_text_only(self) -> None:
        msgs = build_messages("Hello", [], _AGENT, _MODEL)
        assert len(msgs) == 1
        assert msgs[0].message_type == MessageType.chat

    def test_tool_calls_only(self) -> None:
        tcs = [
            {"id": "c1", "function": {"name": "tool_a", "arguments": "{}"}},
            {"id": "c2", "function": {"name": "tool_b", "arguments": "{}"}},
        ]
        msgs = build_messages("", tcs, _AGENT, _MODEL)
        assert len(msgs) == 2
        assert all(m.message_type == MessageType.system for m in msgs)

    def test_mixed_text_and_tool_call(self) -> None:
        tcs = [{"id": "c1", "function": {"name": "tool_a", "arguments": "{}"}}]
        msgs = build_messages("Some text", tcs, _AGENT, _MODEL)
        assert len(msgs) == 2
        assert msgs[0].message_type == MessageType.chat
        assert msgs[1].message_type == MessageType.system

    def test_empty_returns_empty_list(self) -> None:
        assert build_messages("", [], _AGENT, _MODEL) == []


def _make_descriptor(name: str) -> ToolDescriptor:
    async def _executor(_args: dict[str, object]) -> ToolResult:
        return ToolResult(content="ok")

    return ToolDescriptor(
        name=name,
        description=f"{name} description",
        parameters={"type": "object", "properties": {}},
        factory=lambda _cwd: _executor,
    )


class TestBuildToolSchemas:
    def test_maps_descriptors_to_openai_shape(self) -> None:
        descriptors = [_make_descriptor("read_file"), _make_descriptor("write_file")]
        schemas = build_tool_schemas(descriptors)
        assert schemas == [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "read_file description",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "write_file description",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
        ]

    def test_parameters_passed_through_unchanged(self) -> None:
        params = {"type": "object", "properties": {"x": {"type": "integer"}}, "required": ["x"]}
        descriptor = ToolDescriptor(
            name="t",
            description="d",
            parameters=params,
            factory=lambda _cwd: lambda _args: None,  # type: ignore[arg-type,return-value]
        )
        schemas = build_tool_schemas([descriptor])
        assert schemas[0]["function"]["parameters"] is params

    def test_empty_list_returns_empty_list(self) -> None:
        assert build_tool_schemas([]) == []


class TestBuildAssistantHistoryEntry:
    def test_text_only(self) -> None:
        entry = build_assistant_history_entry("Hello", [])
        assert entry == {"role": "assistant", "content": "Hello"}

    def test_tool_calls_only_empty_text(self) -> None:
        tcs = [{"id": "c1", "function": {"name": "tool_a", "arguments": "{}"}}]
        entry = build_assistant_history_entry("", tcs)
        assert entry == {"role": "assistant", "content": None, "tool_calls": tcs}

    def test_mixed_text_and_tool_calls(self) -> None:
        tcs = [{"id": "c1", "function": {"name": "tool_a", "arguments": "{}"}}]
        entry = build_assistant_history_entry("Some text", tcs)
        assert entry == {"role": "assistant", "content": "Some text", "tool_calls": tcs}


class TestBuildToolResultEntry:
    def test_exact_shape(self) -> None:
        entry = build_tool_result_entry("call_1", "the result")
        assert entry == {"role": "tool", "tool_call_id": "call_1", "content": "the result"}
