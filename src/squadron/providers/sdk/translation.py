"""Translate SDK message types to squadron Message objects."""

from __future__ import annotations

from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
)

from squadron.core.models import SDK_RESULT_TYPE, Message, MessageType


def translate_sdk_message(sdk_msg: Any, sender: str) -> list[Message]:
    """Convert an SDK message into zero or more squadron Messages.

    An ``AssistantMessage`` may contain multiple content blocks, each of
    which becomes its own squadron ``Message``.  Other SDK types
    produce at most one ``Message``.  Unrecognised types return an empty
    list.
    """
    if isinstance(sdk_msg, AssistantMessage):
        return _translate_assistant(sdk_msg, sender)
    if isinstance(sdk_msg, ToolResultBlock):
        return [_translate_tool_result(sdk_msg, sender)]
    if isinstance(sdk_msg, ResultMessage):
        return [_translate_result(sdk_msg, sender)]
    return []


# -- private helpers -------------------------------------------------------


def _translate_assistant(msg: AssistantMessage, sender: str) -> list[Message]:
    messages: list[Message] = []
    for block in msg.content:
        if isinstance(block, TextBlock):
            messages.append(
                Message(
                    sender=sender,
                    recipients=["all"],
                    content=block.text,
                    message_type=MessageType.chat,
                    metadata={"sdk_type": "assistant_text"},
                )
            )
        elif isinstance(block, ToolUseBlock):
            messages.append(
                Message(
                    sender=sender,
                    recipients=["all"],
                    content=f"Using tool: {block.name}",
                    message_type=MessageType.system,
                    metadata={
                        "sdk_type": "tool_use",
                        "tool_name": block.name,
                        "tool_input": block.input,
                    },
                )
            )
        # Unknown block types (e.g. ThinkingBlock) are silently skipped.
    return messages


def _translate_tool_result(block: ToolResultBlock, sender: str) -> Message:
    return Message(
        sender=sender,
        recipients=["all"],
        content=str(block.content),
        message_type=MessageType.system,
        metadata={"sdk_type": "tool_result"},
    )


def _translate_result(msg: ResultMessage, sender: str) -> Message:
    content = getattr(msg, "result", None) or str(msg)
    if msg.subtype == "success":
        return Message(
            sender=sender,
            recipients=["all"],
            content=content,
            message_type=MessageType.chat,
            metadata={"sdk_type": SDK_RESULT_TYPE, "subtype": "success"},
        )
    return Message(
        sender=sender,
        recipients=["all"],
        content=content,
        message_type=MessageType.system,
        metadata={"sdk_type": SDK_RESULT_TYPE, "subtype": msg.subtype},
    )
