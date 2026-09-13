"""OpenAICompatibleAgent — conversational agent via OpenAI Chat Completions API."""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator, Sequence
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
from squadron.tools import ToolExecutor, ToolResult, limits

_log = get_logger("squadron.providers.openai.agent")

# Extra delta field OpenRouter-compatible backends use to stream a reasoning model's
# thinking. Not part of the OpenAI SDK's typed ChoiceDelta; read via model_extra.
_REASONING_DELTA_FIELD = "reasoning"


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


def _require_final_content(turn: TurnResult, *, tool_calls_made: int = 0) -> None:
    """Refuse a final turn that carries neither text nor tool calls.

    ``translation.build_messages`` yields no Message for empty text, so without this
    an empty turn reaches the caller as *nothing*: no content, no tool telemetry, and
    a review that records UNKNOWN with an empty raw output and no clue why. The
    finish reason and reasoning volume are the only evidence the stream offers, so
    they ride the error.
    """
    if not turn.is_empty():
        return
    _log.warning(
        "Model returned an empty final turn (finish_reason=%r, reasoning_chars=%d)",
        turn.finish_reason,
        turn.reasoning_chars,
    )
    raise ProviderError(
        f"Model returned an empty final turn (finish_reason={turn.finish_reason!r}, "
        f"reasoning_chars={turn.reasoning_chars}); no response to deliver.",
        tool_calls_made=tool_calls_made,
    )


@dataclass(frozen=True)
class TurnResult:
    """Raw aggregated output of a single streamed API turn.

    Internal plumbing between ``_stream_turn`` and its callers — not translated into
    caller-facing Messages and not appended to history by ``_stream_turn`` itself.
    """

    text: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])
    # Why the backend stopped, from the last chunk that carried one. Needed to explain
    # an empty turn: a model whose output budget went entirely to reasoning ends with
    # finish_reason="length" and no content.
    finish_reason: str | None = None
    # Characters of reasoning streamed outside ``delta.content``. OpenRouter-style
    # backends put a reasoning model's thinking in an extra ``reasoning`` field the
    # SDK's typed delta does not declare; it is never surfaced, only measured, so an
    # empty turn can be told apart from a silent one.
    reasoning_chars: int = 0

    def is_empty(self) -> bool:
        """True when the turn carries nothing a caller can act on."""
        return not self.tool_calls and not self.text.strip()


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
        tools_suppressed_reason: str | None = None,
        cwd: str | None = None,
        tool_exclude_patterns: Sequence[str] | None = None,
        max_tool_iterations: int | None = None,
        max_history_chars: int | None = None,
        max_tool_result_chars: int | None = None,
    ) -> None:
        self._name = name
        self._client = client
        self._model = model
        self._history: list[dict[str, Any]] = []
        self._history_chars = 0
        self._state = AgentState.idle
        self._cwd = cwd
        # Opaque to this agent: a sequence of path patterns to withhold from the tool jail,
        # threaded to ``materialize`` exactly as ``cwd`` is. The agent is a generic provider
        # and deliberately does not know why any pattern is here or what a review type is
        # (design D5) — the caller decides policy, this only carries it.
        self._tool_exclude_patterns = tuple(tool_exclude_patterns or ())
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
        # Clamped up to the floor: a configured value below what a tool itself returns
        # would re-truncate correct results instead of bounding runaway ones.
        self._max_tool_result_chars = limits.resolve_tool_result_cap(
            max_tool_result_chars
            if max_tool_result_chars is not None
            else _int_key_default("agent.max_tool_result_chars")
        )

        requested_tools = allowed_tools or []
        if requested_tools and cwd is None:
            raise ProviderError(
                f"allowed_tools {requested_tools!r} configured but cwd is None; "
                "tool-capable agents require an explicit working directory."
            )

        self._tool_executors: dict[str, ToolExecutor] = {}
        self._tool_schemas: list[dict[str, object]] = []
        # Empty when no tools were configured. The telemetry stamp distinguishes "offered
        # but unused" from "never offered" (design D5), so the two cases must not collapse.
        self._tools_given: list[str] = []
        # Set only when the capability gate emptied a non-empty declared set (slice 266).
        # This is the third state slice 265 never needed: without it, a suppressed run and
        # a run that declared no tools persist identically.
        self._tools_suppressed_reason = tools_suppressed_reason
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
            self._tools_given = known_names
            self._tool_executors = tools.materialize(known_names, cwd, self._tool_exclude_patterns)
            descriptors = [d for n in known_names if (d := tools.lookup(n)) is not None]
            self._tool_schemas = translation.build_tool_schemas(descriptors)

        # Composed after tool resolution so the block names the tools the agent actually
        # holds, and composed here rather than at the four call sites (design D1) so no
        # tool-passing caller can skip it. Built once; the turn loop never rebuilds it.
        composed_prompt = tools.compose_system_prompt(system_prompt, self._tools_given)
        if composed_prompt is not None:
            self._append_history({"role": "system", "content": composed_prompt})

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
                _require_final_content(turn, tool_calls_made=0)
                messages = translation.build_messages(
                    turn.text, turn.tool_calls, self._name, self._model
                )
                # Reached only when no tools were configured at all, so this stamps nothing
                # (_stamp_tool_telemetry returns early on an empty tools_given). Kept so the
                # two branches stay symmetrical: if this path ever becomes reachable with
                # tools configured, it already carries the zero-calls telemetry. The genuine
                # "offered tools, called none" case runs through _run_agentic_loop below.
                self._stamp_tool_telemetry(messages, tool_calls_made=0, turn=turn, failed_tool_calls=0)
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
        finish_reason: str | None = None
        reasoning_chars = 0

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
            choice = chunk.choices[0]
            if choice.finish_reason is not None:
                finish_reason = choice.finish_reason
            delta = choice.delta
            if delta.content:
                text_buffer += delta.content
            reasoning = (delta.model_extra or {}).get(_REASONING_DELTA_FIELD)
            if isinstance(reasoning, str):
                reasoning_chars += len(reasoning)
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
        return TurnResult(
            text=text_buffer,
            tool_calls=tool_calls_list,
            finish_reason=finish_reason,
            reasoning_chars=reasoning_chars,
        )

    async def _execute_tool_call(self, tool_call: dict[str, Any]) -> tuple[str, bool]:
        """Execute one model-issued tool call; return its content and whether it failed.

        Never raises: malformed arguments, an unknown tool name, and an executor
        that raises are all converted to an error content string so the loop can
        hand the failure back to the model instead of crashing (arch §Tool
        argument validation).

        The boolean is returned rather than recovered downstream because the only
        other way to know is to match on the ``"Error: "`` prefix of the content,
        and dispatching on a human-readable string breaks the moment a message is
        reworded. Every path that hands the model a failure reports ``True`` — the
        count means "tool calls that failed", not "calls whose executor returned
        ``is_error``", so the pre-executor rejections below are counted too.
        """
        function = tool_call.get("function", {})
        tool_name = function.get("name", "")
        raw_arguments = function.get("arguments", "")

        try:
            parsed: object = json.loads(raw_arguments) if raw_arguments else {}
        except json.JSONDecodeError as exc:
            # Truncated: a model can emit an arbitrarily large argument string (a
            # degenerate repetition loop produced ~400KB in practice), and logging it
            # whole floods the operator's terminal and the log file.
            _log.warning(
                "Tool call %r has malformed JSON arguments (%s): %.200r",
                tool_name,
                exc,
                raw_arguments,
            )
            return f"Error: arguments for tool '{tool_name}' are not valid JSON: {exc}", True

        # Executors take a keyword mapping; valid JSON of any other shape (a list,
        # a bare scalar) is still an unusable argument set.
        if not isinstance(parsed, dict):
            _log.warning(
                "Tool call %r arguments are %s, not a JSON object: %.200r",
                tool_name,
                type(parsed).__name__,
                raw_arguments,
            )
            return f"Error: arguments for tool '{tool_name}' must be a JSON object.", True
        arguments = cast(dict[str, object], parsed)

        executor = self._tool_executors.get(tool_name)
        if executor is None:
            allowed = list(self._tool_executors)
            _log.warning(
                "Model called unknown tool %r; allowed tools: %s",
                tool_name,
                allowed,
            )
            return f"Error: tool '{tool_name}' is not available. Allowed tools: {allowed}", True

        try:
            result: ToolResult = await executor(arguments)
        except Exception:  # noqa: BLE001 — executor contract says never raise; this is
            # defense against a future/MCP-bridged tool violating it (design §Error
            # surfacing), converted to a tool-result error rather than crashing the loop.
            _log.exception("Tool %r raised during execution", tool_name)
            return (
                f"Error: tool '{tool_name}' raised an unexpected exception during execution.",
                True,
            )

        if result.is_error:
            _log.info("Tool %r returned an error result: %s", tool_name, result.content)
        else:
            _log.debug(
                "Tool %r succeeded (args=%r, result=%.200r)",
                tool_name,
                arguments,
                result.content,
            )
        return result.content, result.is_error

    async def _run_agentic_loop(self) -> list[Message]:
        """Drive turns until the model stops calling tools, or a guard fires.

        Only the no-``tool_calls`` exit translates a turn into caller-facing Messages
        (design §Control flow) — intermediate turns are appended to history and
        executed against, but never yielded.
        """
        max_iterations = self._max_tool_iterations
        max_history_chars = self._max_history_chars
        budget_guard_fired = False
        tool_calls_made = 0
        failed_tool_calls = 0

        for _iteration in range(max_iterations):
            # Tools are withdrawn once either budget is spent: each notice asks the
            # model to finalize, and continuing to advertise tool_schemas would let it
            # ignore that and keep calling tools anyway.
            #
            # The final iteration is reserved for the model to answer with the tool
            # results it already has. Without this the loop can only end by the model
            # volunteering to stop, and a model that keeps calling tools loses every
            # result it gathered when the iteration guard fires.
            iterations_left = max_iterations - _iteration
            finalize_now = budget_guard_fired or iterations_left <= 1
            turn_tool_schemas = None if finalize_now else self._tool_schemas

            # The notice goes in *before* the turn it applies to, so the model sees why
            # its tools disappeared. Appending it afterwards would explain the withdrawal
            # only to a turn that had already happened.
            if iterations_left == 1 and not budget_guard_fired:
                _log.warning(
                    "Agentic loop reached its last of %d iterations; withdrawing tools "
                    "and asking the model to finalize with what it has",
                    max_iterations,
                )
                self._append_history(
                    {
                        "role": "user",
                        "content": (
                            "System notice: the tool-iteration budget is exhausted. "
                            "Finalize your response now using the results you already "
                            "have; no more tools will be offered."
                        ),
                    }
                )

            turn = await self._stream_turn(self._history, tool_schemas=turn_tool_schemas)
            self._append_history(translation.build_assistant_history_entry(turn.text, turn.tool_calls))

            if not turn.tool_calls:
                _require_final_content(turn, tool_calls_made=tool_calls_made)
                messages = translation.build_messages(turn.text, [], self._name, self._model)
                self._stamp_tool_telemetry(
                    messages,
                    tool_calls_made=tool_calls_made,
                    turn=turn,
                    failed_tool_calls=failed_tool_calls,
                )
                return messages

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
                content, tool_call_failed = await self._execute_tool_call(tool_call)
                tool_calls_made += 1
                if tool_call_failed:
                    failed_tool_calls += 1
                # Capped per result, before the append: the whole-conversation budget guard
                # below is a backstop for accumulated history, and a single tool result must
                # not be able to exhaust it on its own (SC9). Read as a module attribute at
                # call time so tests can patch it.
                max_result_chars = self._max_tool_result_chars
                if len(content) > max_result_chars:
                    _log.warning(
                        "Tool result for %s was %d characters, truncating to %d",
                        tool_call.get("function", {}).get("name", ""),
                        len(content),
                        max_result_chars,
                    )
                    content = (
                        content[:max_result_chars]
                        + f"\n[truncated: tool result was {len(content)} characters, "
                        f"showing first {max_result_chars}]"
                    )
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

    def _stamp_tool_telemetry(
        self,
        messages: list[Message],
        *,
        tool_calls_made: int,
        turn: TurnResult,
        failed_tool_calls: int,
    ) -> None:
        """Stamp tool-use telemetry and stop-reason evidence on the final Message.

        Only the final Message carries it: intermediate turns are never surfaced to callers
        (slice 262's contract), so anything stamped earlier would be discarded. When no tools
        were configured the tool keys are absent entirely — a caller must be able to tell
        "offered three tools, called none" apart from "never had tools" (design D5).

        Slice 266 adds a third state: tools were declared but the capability gate emptied
        them. That case has an empty ``_tools_given``, so it is stamped independently of the
        two keys above — the early return below must not swallow it.

        Slice 918 adds the stop reason, the reasoning volume, and the failed-call count.
        Those three are stamped *before* the tools early return and unconditionally, on a
        clean completion as much as a degraded one: the case where the stop reason is the
        whole diagnosis is a run that produced text nobody could parse, which returns
        normally and would record nothing if stamping were conditional on failure. The
        values are read off ``turn`` here rather than returned to the caller, so
        ``TurnResult`` stays the internal plumbing its docstring promises.
        """
        if not messages:
            return
        messages[-1].metadata["stop_reason"] = turn.finish_reason
        messages[-1].metadata["reasoning_chars"] = turn.reasoning_chars
        messages[-1].metadata["failed_tool_calls"] = failed_tool_calls
        if self._tools_suppressed_reason is not None:
            messages[-1].metadata["tools_suppressed_reason"] = self._tools_suppressed_reason
        if not self._tools_given:
            return
        messages[-1].metadata["tools_given"] = list(self._tools_given)
        messages[-1].metadata["tool_calls_made"] = tool_calls_made

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
