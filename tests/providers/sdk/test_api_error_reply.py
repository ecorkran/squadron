"""An API-error reply from the CLI is a provider failure, not model output (issue #325).

When a call fails at the API (a usage limit, a bad login, a server error) the CLI
reports it as an assistant message from the ``<synthetic>`` model whose ``error``
field names the failure and whose text is the CLI's notice, e.g. "You've hit your
5-hour limit · resets 11:20am". The agent must raise, not hand that text to the
caller as the model's reply.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
)
from claude_agent_sdk.types import AssistantMessageError

from squadron.core.models import AgentState, Message
from squadron.providers.errors import (
    ProviderAPIError,
    ProviderAuthError,
    ProviderError,
    ProviderRateLimitError,
)
from squadron.providers.sdk.agent import ClaudeSDKAgent

_QUERY = "squadron.providers.sdk.agent.sdk_query"
_CLIENT = "squadron.providers.sdk.agent.ClaudeSDKClient"
_LIMIT_TEXT = "You've hit your 5-hour limit · resets 11:20am (America/Denver)"


def _api_error_reply(error: AssistantMessageError, text: str) -> AssistantMessage:
    """The shape the CLI emits for a failed API call (seen in a real transcript)."""
    return AssistantMessage(content=[TextBlock(text=text)], model="<synthetic>", error=error)


def _error_result() -> ResultMessage:
    return ResultMessage(
        subtype="success",
        duration_ms=10,
        duration_api_ms=0,
        is_error=True,
        num_turns=1,
        session_id="sess-1",
        result=_LIMIT_TEXT,
        api_error_status=429,
    )


def _stream(*messages: object):
    async def gen(*, prompt: str, options: object = None) -> AsyncIterator[object]:
        for message in messages:
            yield message

    return gen


@pytest.fixture
def input_message() -> Message:
    return Message(sender="user", recipients=["bot"], content="Review this code.")


@pytest.fixture
def query_agent() -> ClaudeSDKAgent:
    return ClaudeSDKAgent(name="bot", options=ClaudeAgentOptions(), mode="query")


async def _drain(agent: ClaudeSDKAgent, message: Message, seen: list[Message]) -> None:
    async for reply in agent.handle_message(message):
        seen.append(reply)


@pytest.mark.asyncio
async def test_usage_limit_reply_raises_with_the_cli_notice(
    query_agent: ClaudeSDKAgent, input_message: Message
) -> None:
    seen: list[Message] = []
    gen = _stream(_api_error_reply("rate_limit", _LIMIT_TEXT), _error_result())
    with patch(_QUERY, side_effect=gen), pytest.raises(ProviderRateLimitError) as caught:
        await _drain(query_agent, input_message, seen)

    assert _LIMIT_TEXT in str(caught.value)
    assert not any(_LIMIT_TEXT in reply.content for reply in seen)
    assert query_agent.state == AgentState.failed


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "expected"),
    [
        ("authentication_failed", ProviderAuthError),
        ("billing_error", ProviderAPIError),
        ("invalid_request", ProviderAPIError),
        ("server_error", ProviderAPIError),
        ("unknown", ProviderAPIError),
    ],
)
async def test_other_api_error_replies_raise(
    query_agent: ClaudeSDKAgent,
    input_message: Message,
    error: AssistantMessageError,
    expected: type[ProviderError],
) -> None:
    gen = _stream(_api_error_reply(error, "API Error: something failed"))
    with patch(_QUERY, side_effect=gen), pytest.raises(expected):
        await _drain(query_agent, input_message, [])


@pytest.mark.asyncio
async def test_client_mode_raises_so_no_recovery_turn_follows(input_message: Message) -> None:
    agent = ClaudeSDKAgent(name="bot", options=ClaudeAgentOptions(), mode="client")
    client = AsyncMock()

    def receive_response() -> AsyncIterator[object]:
        return _stream(_api_error_reply("rate_limit", _LIMIT_TEXT))(prompt="")

    client.receive_response = receive_response
    with patch(_CLIENT, return_value=client), pytest.raises(ProviderRateLimitError):
        await _drain(agent, input_message, [])

    assert agent.state == AgentState.failed


@pytest.mark.asyncio
async def test_subagent_error_reply_is_left_to_the_parent(
    query_agent: ClaudeSDKAgent, input_message: Message
) -> None:
    """A subagent's failed call reaches the parent model as a tool result; it decides."""
    subagent_reply = AssistantMessage(
        content=[TextBlock(text="API Error")],
        model="<synthetic>",
        parent_tool_use_id="tool-1",
        error="server_error",
    )
    answer = AssistantMessage(content=[TextBlock(text="the review")], model="claude-haiku-5-5")
    seen: list[Message] = []
    with patch(_QUERY, side_effect=_stream(subagent_reply, answer)):
        await _drain(query_agent, input_message, seen)

    assert any("the review" in reply.content for reply in seen)
