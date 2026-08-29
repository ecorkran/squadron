"""Translation helpers: OpenAI response data → squadron Message objects.

Also hosts the OpenAI wire-protocol shapes for tool schemas and message-history
entries (D5) — one home for the request/response shape prevents drift between
callers that build them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from squadron.core.models import Message, MessageType

if TYPE_CHECKING:
    from squadron.tools import ToolDescriptor


def build_text_message(
    text: str,
    agent_name: str,
    model: str,
) -> Message | None:
    """Return a chat Message for *text*, or ``None`` if text is empty/whitespace."""
    if not text or not text.strip():
        return None
    return Message(
        sender=agent_name,
        recipients=["all"],
        content=text,
        message_type=MessageType.chat,
        metadata={"provider": "openai", "model": model},
    )


def build_tool_call_message(tool_call: dict[str, object], agent_name: str) -> Message:
    """Return a system Message surfacing an OpenAI tool call."""
    function: dict[str, object] = tool_call.get("function", {})  # type: ignore[assignment]
    tool_name = function.get("name", "")
    return Message(
        sender=agent_name,
        recipients=["all"],
        content=f"Tool call: {tool_name}",
        message_type=MessageType.system,
        metadata={
            "provider": "openai",
            "type": "tool_call",
            "tool_call_id": tool_call.get("id", ""),
            "tool_name": tool_name,
            "tool_arguments": function.get("arguments", ""),
        },
    )


def build_messages(
    text_buffer: str,
    tool_calls_list: list[dict[str, object]],
    agent_name: str,
    model: str,
) -> list[Message]:
    """Build the full list of Messages from accumulated text and tool calls.

    Text message comes first (if non-empty), then one system Message per tool call.
    """
    messages: list[Message] = []
    text_msg = build_text_message(text_buffer, agent_name, model)
    if text_msg is not None:
        messages.append(text_msg)
    for tc in tool_calls_list:
        messages.append(build_tool_call_message(tc, agent_name))
    return messages


def build_tool_schemas(descriptors: list[ToolDescriptor]) -> list[dict[str, object]]:
    """Map tool descriptors to the OpenAI ``tools[]`` request shape."""
    return [
        {
            "type": "function",
            "function": {
                "name": d.name,
                "description": d.description,
                "parameters": d.parameters,
            },
        }
        for d in descriptors
    ]


def build_assistant_history_entry(
    text: str,
    tool_calls: list[dict[str, object]],
) -> dict[str, object]:
    """Build the assistant turn's history entry in OpenAI format.

    ``content`` is ``None`` when ``text`` is empty and ``tool_calls`` are present;
    otherwise a plain ``{"role": "assistant", "content": text}`` entry.
    """
    if tool_calls:
        return {
            "role": "assistant",
            "content": text if text else None,
            "tool_calls": tool_calls,
        }
    return {"role": "assistant", "content": text}


def build_tool_result_entry(tool_call_id: str, content: str) -> dict[str, object]:
    """Build a ``role: "tool"`` history entry for a single tool-call result."""
    return {"role": "tool", "tool_call_id": tool_call_id, "content": content}
