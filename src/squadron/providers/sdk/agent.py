"""ClaudeSDKAgent — wraps claude-agent-sdk for task execution."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ClaudeSDKError,
    CLIConnectionError,
    CLIJSONDecodeError,
    CLINotFoundError,
    ProcessError,
)
from claude_agent_sdk import (
    query as sdk_query,
)
from claude_agent_sdk._errors import (  # pyright: ignore[reportPrivateUsage]
    MessageParseError,
)

from squadron.core.models import AgentState, Message
from squadron.logging import get_logger
from squadron.providers.errors import (
    ProviderAPIError,
    ProviderAuthError,
    ProviderError,
    ProviderRateLimitError,
)
from squadron.providers.sdk.translation import translate_sdk_message

_MAX_RATE_LIMIT_RETRIES = 10

#: Exponential backoff between rate-limit retries, in seconds: 2, 4, 8, ...
#: capped at ``_RATE_LIMIT_MAX_BACKOFF_S``.
#:
#: This previously did not exist. The retry loops carried a comment saying
#: "the CLI handles the backoff delay" and slept for nothing — measured at
#: 11 attempts in 0.1ms, which hammers the rate limiter rather than waiting
#: for it and can *cause* the limit it is trying to survive.
_RATE_LIMIT_BASE_BACKOFF_S = 2.0
_RATE_LIMIT_MAX_BACKOFF_S = 60.0


def _rate_limit_backoff_s(attempt: int) -> float:
    """Seconds to wait before rate-limit retry ``attempt`` (1-based)."""
    return min(_RATE_LIMIT_BASE_BACKOFF_S * (2 ** (attempt - 1)), _RATE_LIMIT_MAX_BACKOFF_S)


class ClaudeSDKAgent:
    """An autonomous agent backed by claude-agent-sdk."""

    def __init__(
        self,
        name: str,
        options: ClaudeAgentOptions,
        mode: str = "query",
    ) -> None:
        self._name = name
        self._options = options
        self._mode = mode
        self._state = AgentState.idle
        self._client: ClaudeSDKClient | None = None
        self._log = get_logger(f"squadron.providers.sdk.agent.{name}")

    # -- Protocol properties ------------------------------------------------

    @property
    def name(self) -> str:
        return self._name

    @property
    def agent_type(self) -> str:
        return "sdk"

    @property
    def state(self) -> AgentState:
        return self._state

    # -- Message handling ---------------------------------------------------

    async def handle_message(self, message: Message) -> AsyncIterator[Message]:
        """Route to query or client mode based on configuration."""
        if self._mode == "client":
            async for msg in self._handle_client_mode(message):
                yield msg
        else:
            async for msg in self._handle_query_mode(message):
                yield msg

    async def _skip_unparseable(self, stream: AsyncIterator[Any]) -> AsyncIterator[Any]:
        """Yield SDK messages, skipping ones this SDK version cannot parse.

        The bundled CLI emits message types newer than the installed SDK's
        parser knows — ``rate_limit_event`` is the observed case, an
        informational notice the CLI handles its own backoff for. The parser
        raises ``MessageParseError`` on any unrecognized type, which would
        otherwise kill a working run.

        Skipping in place is what keeps the run alive: the enclosing retry
        loops restart the *whole query*, so treating this as a retryable
        error would discard everything done so far — on a long audit, tens
        of tool calls and several minutes of work.

        Only parse failures are swallowed. Connection errors, process
        failures, and every other ``ClaudeSDKError`` propagate untouched.
        """
        iterator = stream.__aiter__()
        while True:
            try:
                sdk_msg = await iterator.__anext__()
            except StopAsyncIteration:
                return
            except MessageParseError as exc:
                self._log.warning(
                    "Skipping SDK message this version cannot parse (%s); stream continues.",
                    exc,
                )
                continue
            yield sdk_msg

    async def _handle_query_mode(self, message: Message) -> AsyncIterator[Message]:
        """One-shot execution via ``sdk_query``.

        Retries the full query on a ``rate_limit_event``, waiting an
        exponentially increasing delay first. The delay is not optional:
        retrying immediately hammers the limiter and can cause the very
        limit it is trying to survive.
        """
        self._state = AgentState.processing
        retries = 0
        while True:
            try:
                stream = sdk_query(prompt=message.content, options=self._options)
                async for sdk_msg in self._skip_unparseable(stream):
                    for translated in translate_sdk_message(sdk_msg, sender=self._name):
                        yield translated
                self._state = AgentState.idle
                return
            except CLINotFoundError as exc:
                self._state = AgentState.failed
                raise ProviderAuthError(str(exc)) from exc
            except ProcessError as exc:
                self._state = AgentState.failed
                raise ProviderAPIError(str(exc), status_code=getattr(exc, "exit_code", None)) from exc
            except ClaudeSDKError as exc:
                if "rate_limit_event" in str(exc) and retries < _MAX_RATE_LIMIT_RETRIES:
                    retries += 1
                    delay = _rate_limit_backoff_s(retries)
                    self._log.warning(
                        "Rate limited (attempt %d/%d); waiting %.0fs before retry.",
                        retries,
                        _MAX_RATE_LIMIT_RETRIES,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                self._state = AgentState.failed
                if "rate_limit" in str(exc):
                    raise ProviderRateLimitError(str(exc)) from exc
                raise ProviderError(str(exc)) from exc

    async def _handle_client_mode(self, message: Message) -> AsyncIterator[Message]:
        """Multi-turn execution via ``ClaudeSDKClient``.

        Includes rate-limit retry logic: when the CLI emits a
        ``rate_limit_event`` the SDK raises ``ClaudeSDKError``. We wait an
        exponentially increasing delay, then restart ``receive_response()``
        on the same session (the underlying channel remains intact), up to
        ``_MAX_RATE_LIMIT_RETRIES`` times.
        """
        self._state = AgentState.processing
        try:
            if self._client is None:
                self._client = ClaudeSDKClient(options=self._options)
                await self._client.connect()
            await self._client.query(prompt=message.content)
            retries = 0
            while True:
                try:
                    async for sdk_msg in self._skip_unparseable(self._client.receive_response()):
                        for translated in translate_sdk_message(sdk_msg, sender=self._name):
                            yield translated
                    break  # normal completion
                except ClaudeSDKError as exc:
                    if "rate_limit_event" in str(exc) and retries < _MAX_RATE_LIMIT_RETRIES:
                        retries += 1
                        delay = _rate_limit_backoff_s(retries)
                        self._log.warning(
                            "Rate limited (attempt %d/%d); waiting %.0fs before retry.",
                            retries,
                            _MAX_RATE_LIMIT_RETRIES,
                            delay,
                        )
                        await asyncio.sleep(delay)
                        continue
                    raise
            self._state = AgentState.idle
        except CLINotFoundError as exc:
            self._state = AgentState.failed
            raise ProviderAuthError(str(exc)) from exc
        except ProcessError as exc:
            self._state = AgentState.failed
            raise ProviderAPIError(str(exc), status_code=getattr(exc, "exit_code", None)) from exc
        except (CLIConnectionError, CLIJSONDecodeError, ClaudeSDKError) as exc:
            self._state = AgentState.failed
            raise ProviderError(str(exc)) from exc

    # -- Lifecycle ----------------------------------------------------------

    async def shutdown(self) -> None:
        """Disconnect client if in multi-turn mode."""
        if self._client is not None:
            try:
                await self._client.disconnect()
            except Exception:
                pass  # Best-effort cleanup
            self._client = None
        self._state = AgentState.terminated
