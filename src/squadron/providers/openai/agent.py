"""OpenAICompatibleAgent — conversational agent via OpenAI Chat Completions API."""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, cast

import openai
from openai import AsyncOpenAI, AsyncStream, omit
from openai.types.chat import (
    ChatCompletionChunk,
    ChatCompletionMessageParam,
    ChatCompletionToolUnionParam,
)

# squadron.tools (the package, not squadron.tools.registry) is imported for its
# registration side effect: it guarantees built-in tools are registered before this
# module's constructor calls registry.lookup/materialize.
import squadron.tools as tools
from squadron.config.keys import CONFIG_KEYS
from squadron.core.models import AgentState, Message
from squadron.logging import get_logger
from squadron.providers.errors import (
    ProviderAPIError,
    ProviderAuthError,
    ProviderError,
    ProviderTimeoutError,
)
from squadron.providers.openai import translation
from squadron.tools import ToolExecutor, ToolResult

_log = get_logger("squadron.providers.openai.agent")


def _entry_chars(entry: dict[str, Any]) -> int:
    """Return the character size of one history entry.

    Counts the payload actually sent on the wire — message content plus any
    tool-call arguments — so ``agent.max_history_chars`` means what its config
    description says ("message-history size (characters)"). A whole-dict ``str()``
    would also count dict-repr punctuation and key names.
    """
    total = len(str(entry.get("content", "") or ""))
    tool_calls: list[dict[str, Any]] = entry.get("tool_calls") or []
    for tool_call in tool_calls:
        function: dict[str, Any] = tool_call.get("function") or {}
        total += len(str(function.get("name") or ""))
        total += len(str(function.get("arguments") or ""))
    return total


def _int_key_default(key: str) -> int:
    """Return a registered ConfigKey's declared default, without touching config files."""
    default = CONFIG_KEYS[key].default
    if not isinstance(default, int):
        raise TypeError(f"config key {key!r} default must be an int, got {default!r}")
    return default


@dataclass(frozen=True)
class TurnResult:
    """Raw aggregated output of a single streamed API turn.

    Internal plumbing between ``_stream_turn`` and its callers — not translated into
    caller-facing Messages and not appended to history by ``_stream_turn`` itself.
    """

    text: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])


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
        max_tool_iterations: int | None = None,
        max_history_chars: int | None = None,
    ) -> None:
        self._name = name
        self._client = client
        self._model = model
        self._history: list[dict[str, Any]] = []
        self._history_chars = 0
        self._state = AgentState.idle
        self._cwd = cwd
        # Loop bounds are resolved by the caller (the provider reads user config) so
        # that no config file I/O happens inside an async turn. Falling back to the
        # registered ConfigKey default keeps the single source of truth in keys.py.
        self._max_tool_iterations = (
            max_tool_iterations
            if max_tool_iterations is not None
            else _int_key_default("agent.max_tool_iterations")
        )
        self._max_history_chars = (
            max_history_chars
            if max_history_chars is not None
            else _int_key_default("agent.max_history_chars")
        )

        if system_prompt is not None:
            self._append_history({"role": "system", "content": system_prompt})

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
            # An unknown name is a configuration error, not something to route around:
            # silently dropping it produces a confident review by a model that could not read
            # any of the files it was asked about (design D3). Every unknown name is reported
            # at once so a mis-declared template is fixed in one pass.
            unknown = [name for name in requested_tools if tools.lookup(name) is None]
            if unknown:
                raise ProviderError(
                    f"Unknown tool name(s) in allowed_tools: {', '.join(unknown)}. "
                    f"Registered tools: {', '.join(sorted(tools.list_tools()))}."
                )
            known_names: list[str] = list(requested_tools)
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
        self._append_history({"role": "user", "content": message.content})
        try:
            if not self._tool_executors:
                turn = await self._stream_turn(self._history, tool_schemas=None)
                self._append_history(
                    translation.build_assistant_history_entry(turn.text, turn.tool_calls)
                )
                messages = translation.build_messages(
                    turn.text, turn.tool_calls, self._name, self._model
                )
            else:
                messages = await self._run_agentic_loop()
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

        # Arguments are passed explicitly rather than unpacked from a dict[str, Any]:
        # **kwargs unpacking erases the SDK's typed overload, leaving the whole
        # chunk-aggregation block below untyped.
        stream: AsyncStream[ChatCompletionChunk] = await self._client.chat.completions.create(
            model=self._model,
            messages=cast(list[ChatCompletionMessageParam], messages),
            stream=True,
            extra_body=extra_body,
            tools=cast(list[ChatCompletionToolUnionParam], tool_schemas) if tool_schemas else omit,
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

    async def _execute_tool_call(self, tool_call: dict[str, Any]) -> str:
        """Execute one model-issued tool call and return its result content.

        Never raises: malformed arguments, an unknown tool name, and an executor
        that raises are all converted to an error content string so the loop can
        hand the failure back to the model instead of crashing (arch §Tool
        argument validation).
        """
        function = tool_call.get("function", {})
        tool_name = function.get("name", "")
        raw_arguments = function.get("arguments", "")

        try:
            parsed: object = json.loads(raw_arguments) if raw_arguments else {}
        except json.JSONDecodeError as exc:
            _log.warning(
                "Tool call %r has malformed JSON arguments (%s): %r",
                tool_name,
                exc,
                raw_arguments,
            )
            return f"Error: arguments for tool '{tool_name}' are not valid JSON: {exc}"

        # Executors take a keyword mapping; valid JSON of any other shape (a list,
        # a bare scalar) is still an unusable argument set.
        if not isinstance(parsed, dict):
            _log.warning(
                "Tool call %r arguments are %s, not a JSON object: %r",
                tool_name,
                type(parsed).__name__,
                raw_arguments,
            )
            return f"Error: arguments for tool '{tool_name}' must be a JSON object."
        arguments = cast(dict[str, object], parsed)

        executor = self._tool_executors.get(tool_name)
        if executor is None:
            allowed = list(self._tool_executors)
            _log.warning(
                "Model called unknown tool %r; allowed tools: %s",
                tool_name,
                allowed,
            )
            return f"Error: tool '{tool_name}' is not available. Allowed tools: {allowed}"

        try:
            result: ToolResult = await executor(arguments)
        except Exception:  # noqa: BLE001 — executor contract says never raise; this is
            # defense against a future/MCP-bridged tool violating it (design §Error
            # surfacing), converted to a tool-result error rather than crashing the loop.
            _log.exception("Tool %r raised during execution", tool_name)
            return f"Error: tool '{tool_name}' raised an unexpected exception during execution."

        if result.is_error:
            _log.info("Tool %r returned an error result: %s", tool_name, result.content)
        else:
            _log.debug(
                "Tool %r succeeded (args=%r, result=%.200r)",
                tool_name,
                arguments,
                result.content,
            )
        return result.content

    async def _run_agentic_loop(self) -> list[Message]:
        """Drive turns until the model stops calling tools, or a guard fires.

        Only the no-``tool_calls`` exit translates a turn into caller-facing Messages
        (design §Control flow) — intermediate turns are appended to history and
        executed against, but never yielded.
        """
        max_iterations = self._max_tool_iterations
        max_history_chars = self._max_history_chars
        budget_guard_fired = False

        for _iteration in range(max_iterations):
            # Once the budget guard has fired, stop offering tools: the notice below
            # asks the model to finalize, and continuing to advertise tool_schemas
            # would let it ignore that and keep calling tools anyway.
            turn_tool_schemas = None if budget_guard_fired else self._tool_schemas
            turn = await self._stream_turn(self._history, tool_schemas=turn_tool_schemas)
            self._append_history(translation.build_assistant_history_entry(turn.text, turn.tool_calls))

            if not turn.tool_calls:
                return translation.build_messages(turn.text, [], self._name, self._model)

            for tool_call in turn.tool_calls:
                tool_call_id = tool_call.get("id", "")
                if not tool_call_id:
                    # An OpenAI-compatible backend streamed a tool call with no id.
                    # Its result could never be matched back to the call, so executing
                    # the tool would run a side effect (write_file, bash) whose output
                    # is undeliverable, and appending the result would leave history
                    # permanently unusable. Fail here instead.
                    tool_name = tool_call.get("function", {}).get("name", "")
                    _log.warning(
                        "Model streamed a tool call with no id (function=%r); "
                        "aborting the turn without executing it",
                        tool_name,
                    )
                    raise ProviderError(
                        f"Model streamed a tool call for {tool_name!r} with no id; "
                        "its result cannot be matched to the call."
                    )
                content = await self._execute_tool_call(tool_call)
                self._append_history(translation.build_tool_result_entry(tool_call_id, content))

            if not budget_guard_fired and self._history_chars > max_history_chars:
                budget_guard_fired = True
                _log.warning(
                    "Agentic loop history exceeded agent.max_history_chars (%d); "
                    "prompting model to finalize",
                    max_history_chars,
                )
                # A plain user-role message, not a fake tool result: a role:"tool"
                # entry must carry a tool_call_id matching a real pending call, and
                # this notice isn't a response to any tool call the model made.
                self._append_history(
                    {
                        "role": "user",
                        "content": (
                            "System notice: the conversation history budget has been "
                            "exceeded. Finalize your response now; no more tools will "
                            "be offered."
                        ),
                    }
                )

        _log.warning(
            "Agentic loop reached agent.max_tool_iterations (%d) without finalizing",
            max_iterations,
        )
        raise ProviderError(
            f"Agentic loop exceeded agent.max_tool_iterations ({max_iterations}) "
            "without the model producing a final response."
        )

    def _append_history(self, entry: dict[str, Any]) -> None:
        """Append a history entry and update the running character count.

        Every append goes through here so the counter cannot drift from the list:
        rescanning the whole history per loop iteration is O(n^2) in turns and does
        CPU-bound work inside an async turn.
        """
        self._history.append(entry)
        self._history_chars += _entry_chars(entry)

    async def shutdown(self) -> None:
        """Close the AsyncOpenAI client and mark as terminated."""
        await self._client.close()
        self._state = AgentState.terminated
