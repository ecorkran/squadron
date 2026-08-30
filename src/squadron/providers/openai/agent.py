"""OpenAICompatibleAgent — conversational agent via OpenAI Chat Completions API."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, cast

import openai
from openai import AsyncOpenAI, AsyncStream
from openai.types.chat import ChatCompletionChunk, ChatCompletionMessageParam

# squadron.tools (the package, not squadron.tools.registry) is imported for its
# registration side effect: it guarantees built-in tools are registered before this
# module's constructor calls registry.lookup/materialize.
import squadron.tools as tools
from squadron.core.models import AgentState, Message
from squadron.logging import get_logger
from squadron.providers.errors import (
    ProviderAPIError,
    ProviderAuthError,
    ProviderError,
    ProviderTimeoutError,
)
from squadron.providers.openai import translation
from squadron.tools import ToolExecutor

_log = get_logger("squadron.providers.openai.agent")


@dataclass(frozen=True)
class TurnResult:
    """Raw aggregated output of a single streamed API turn.

    Internal plumbing between ``_stream_turn`` and its callers — not translated into
    caller-facing Messages and not appended to history by ``_stream_turn`` itself.
    """

    text: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


class OpenAICompatibleAgent:
    """Conversational agent backed by the OpenAI Chat Completions API."""

    def __init__(
        self,
        name: str,
        client: AsyncOpenAI,
        model: str,
        system_prompt: str | None,
        *,
        allowed_tools: list[str] | None = None,
        cwd: str | None = None,
    ) -> None:
        self._name = name
        self._client = client
        self._model = model
        self._history: list[dict[str, Any]] = []
        self._state = AgentState.idle
        self._cwd = cwd

        if system_prompt is not None:
            self._history.append({"role": "system", "content": system_prompt})

        requested_tools = allowed_tools or []
        if requested_tools and cwd is None:
            raise ProviderError(
                f"allowed_tools {requested_tools!r} configured but cwd is None; "
                "tool-capable agents require an explicit working directory."
            )

        self._tool_executors: dict[str, ToolExecutor] = {}
        self._tool_schemas: list[dict[str, object]] = []
        if requested_tools:
            assert cwd is not None  # narrowed by the raise above
            known_names = []
            for tool_name in requested_tools:
                if tools.lookup(tool_name) is None:
                    _log.warning(
                        "Dropping unknown tool %r from allowed_tools; registered tools: %s",
                        tool_name,
                        tools.list_tools(),
                    )
                    continue
                known_names.append(tool_name)
            self._tool_executors = tools.materialize(known_names, cwd)
            descriptors = [d for n in known_names if (d := tools.lookup(n)) is not None]
            self._tool_schemas = translation.build_tool_schemas(descriptors)

    @property
    def name(self) -> str:
        return self._name

    @property
    def agent_type(self) -> str:
        return "api"

    @property
    def state(self) -> AgentState:
        return self._state

    async def handle_message(self, message: Message) -> AsyncIterator[Message]:
        """Append message to history, stream from API, yield response Messages."""
        self._state = AgentState.processing
        self._history.append({"role": "user", "content": message.content})
        try:
            turn = await self._stream_turn(self._history, tool_schemas=None)
            self._history.append(translation.build_assistant_history_entry(turn.text, turn.tool_calls))
            messages = translation.build_messages(turn.text, turn.tool_calls, self._name, self._model)
            for msg in messages:
                yield msg
        except openai.AuthenticationError as exc:
            raise ProviderAuthError(str(exc)) from exc
        except openai.PermissionDeniedError as exc:
            raise ProviderAuthError(str(exc)) from exc
        except openai.RateLimitError as exc:
            raise ProviderAPIError(str(exc), status_code=429) from exc
        except openai.APIStatusError as exc:
            raise ProviderAPIError(str(exc), status_code=exc.status_code) from exc
        except openai.APITimeoutError as exc:
            raise ProviderTimeoutError(str(exc)) from exc
        except openai.APIConnectionError as exc:
            raise ProviderError(str(exc)) from exc
        finally:
            self._state = AgentState.idle

    async def _stream_turn(
        self,
        messages: list[dict[str, Any]],
        tool_schemas: list[dict[str, object]] | None,
    ) -> TurnResult:
        """Issue one streaming request and aggregate its deltas into a TurnResult.

        Pure request/aggregate primitive: does not touch ``self._history`` and does
        not build caller-facing Messages.
        """
        text_buffer = ""
        tool_calls_dict: dict[int, dict[str, Any]] = {}

        app_name = os.environ.get("SQUADRON_APP_NAME")
        extra_body = {"user": app_name} if app_name else None

        create_kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": cast(list[ChatCompletionMessageParam], messages),
            "stream": True,
            "extra_body": extra_body,
        }
        if tool_schemas:
            create_kwargs["tools"] = tool_schemas

        stream: AsyncStream[ChatCompletionChunk] = await self._client.chat.completions.create(
            **create_kwargs
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                text_buffer += delta.content
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls_dict:
                        tool_calls_dict[idx] = {
                            "id": "",
                            "type": "function",
                            "function": {"name": "", "arguments": ""},
                        }
                    if tc.id:
                        tool_calls_dict[idx]["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            tool_calls_dict[idx]["function"]["name"] += tc.function.name
                        if tc.function.arguments:
                            tool_calls_dict[idx]["function"]["arguments"] += tc.function.arguments

        tool_calls_list = [tool_calls_dict[k] for k in sorted(tool_calls_dict)]
        return TurnResult(text=text_buffer, tool_calls=tool_calls_list)

    async def shutdown(self) -> None:
        """Close the AsyncOpenAI client and mark as terminated."""
        await self._client.close()
        self._state = AgentState.terminated
