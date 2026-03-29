"""OpenAICompatibleAgent — conversational agent via OpenAI Chat Completions API."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any, cast

import openai
from openai import AsyncOpenAI, AsyncStream
from openai.types.chat import ChatCompletionChunk, ChatCompletionMessageParam

from squadron.core.models import AgentState, Message
from squadron.logging import get_logger
from squadron.providers.errors import (
    ProviderAPIError,
    ProviderAuthError,
    ProviderError,
    ProviderTimeoutError,
)
from squadron.providers.openai import translation

_log = get_logger("squadron.providers.openai.agent")


class OpenAICompatibleAgent:
    """Conversational agent backed by the OpenAI Chat Completions API."""

    def __init__(
        self,
        name: str,
        client: AsyncOpenAI,
        model: str,
        system_prompt: str | None,
    ) -> None:
        self._name = name
        self._client = client
        self._model = model
        self._history: list[dict[str, Any]] = []
        self._state = AgentState.idle

        if system_prompt is not None:
            self._history.append({"role": "system", "content": system_prompt})

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
            messages = await self._call_api()
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

    async def _call_api(self) -> list[Message]:
        """Call the API, accumulate streaming response, return built Messages."""
        text_buffer = ""
        tool_calls_dict: dict[int, dict[str, Any]] = {}

        app_name = os.environ.get("SQUADRON_APP_NAME")
        extra_body = {"user": app_name} if app_name else None

        stream: AsyncStream[
            ChatCompletionChunk
        ] = await self._client.chat.completions.create(
            model=self._model,
            messages=cast(list[ChatCompletionMessageParam], self._history),
            stream=True,
            extra_body=extra_body,
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
                            tool_calls_dict[idx]["function"]["arguments"] += (
                                tc.function.arguments
                            )

        tool_calls_list = [tool_calls_dict[k] for k in sorted(tool_calls_dict)]
        messages = translation.build_messages(
            text_buffer, tool_calls_list, self._name, self._model
        )
        self._append_assistant_history(text_buffer, tool_calls_list)
        return messages

    def _append_assistant_history(
        self,
        text: str,
        tool_calls: list[dict[str, Any]],
    ) -> None:
        """Append the assistant turn to history in OpenAI format."""
        if tool_calls:
            entry: dict[str, Any] = {
                "role": "assistant",
                "content": text if text else None,
                "tool_calls": tool_calls,
            }
        else:
            entry = {"role": "assistant", "content": text}
        self._history.append(entry)

    async def shutdown(self) -> None:
        """Close the AsyncOpenAI client and mark as terminated."""
        await self._client.close()
        self._state = AgentState.terminated
