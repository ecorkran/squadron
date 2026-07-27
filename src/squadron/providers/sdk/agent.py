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
from squadron.providers.sdk.rate_limit import (
    MAX_RATE_LIMIT_RETRIES,
    RATE_LIMIT_MARKER,
    RATE_LIMIT_MAX_BACKOFF_S,
    rate_limit_backoff_s,
)
from squadron.providers.sdk.translation import translate_sdk_message


class ClaudeSDKAgent:
    """An autonomous agent backed by claude-agent-sdk."""

    def __init__(
        self,
        name: str,
        options: ClaudeAgentOptions,
        mode: str = "query",
        max_rate_limit_retries: int = MAX_RATE_LIMIT_RETRIES,
        rate_limit_cap_s: float = RATE_LIMIT_MAX_BACKOFF_S,
    ) -> None:
        self._name = name
        self._options = options
        self._mode = mode
        self._max_rate_limit_retries = max_rate_limit_retries
        self._rate_limit_cap_s = rate_limit_cap_s
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
        parser knows. The parser raises ``MessageParseError`` on any
        unrecognized type, which would otherwise kill a working run over a
        message that carries nothing the caller needs.

        Skipping in place is what keeps the run alive: the enclosing retry
        loops restart the *whole query*, so treating an unknown message as
        a retryable error would discard everything done so far — on a long
        audit, tens of tool calls and several minutes of work.

        A ``rate_limit_event`` is deliberately **not** skipped. It arrives
        as a parse failure only because this SDK version lacks a case for
        it, but it carries real meaning — the provider is throttling — and
        the caller must back off rather than continue into a stream that has
        stopped producing work. It is re-raised for the retry loop.

        Other parse failures are swallowed. Connection errors, process
        failures, and every other ``ClaudeSDKError`` propagate untouched.
        """
        iterator = stream.__aiter__()
        while True:
            try:
                sdk_msg = await iterator.__anext__()
            except StopAsyncIteration:
                return
            except MessageParseError as exc:
                if RATE_LIMIT_MARKER in str(exc):
                    raise
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
                if RATE_LIMIT_MARKER in str(exc) and retries < self._max_rate_limit_retries:
                    retries += 1
                    delay = rate_limit_backoff_s(retries, self._rate_limit_cap_s)
                    self._log.warning(
                        "Rate limited (attempt %d/%d); waiting %.0fs before retry.",
                        retries,
                        self._max_rate_limit_retries,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                self._state = AgentState.failed
                if RATE_LIMIT_MARKER in str(exc):
                    raise ProviderRateLimitError(str(exc)) from exc
                raise ProviderError(str(exc)) from exc

    async def _handle_client_mode(self, message: Message) -> AsyncIterator[Message]:
        """Multi-turn execution via ``ClaudeSDKClient``.

        Includes rate-limit retry logic: when the CLI emits a
        ``rate_limit_event`` the SDK raises ``ClaudeSDKError``. We wait an
        exponentially increasing delay, then restart ``receive_response()``
        on the same session (the underlying channel remains intact), up to
        ``MAX_RATE_LIMIT_RETRIES`` times.
        """
        self._state = AgentState.processing
        try:
            if self._client is None:
                self._client = ClaudeSDKClient(options=self._options)
                await self._client.connect()
            await self._client.query(prompt=message.content)
            retries = 0
            while True:
                progressed = False
                try:
                    async for sdk_msg in self._skip_unparseable(self._client.receive_response()):
                        progressed = True
                        for translated in translate_sdk_message(sdk_msg, sender=self._name):
                            yield translated
                    break  # normal completion
                except ClaudeSDKError as exc:
                    # A throttle that arrives *after* work came through is a
                    # fresh event, not another attempt at the same blocked
                    # call. Without this reset the budget is a cap on
                    # throttles-per-run rather than on consecutive failures,
                    # so a long audit exhausts it while still making progress.
                    if progressed:
                        retries = 0
                    if RATE_LIMIT_MARKER in str(exc) and retries < self._max_rate_limit_retries:
                        retries += 1
                        delay = rate_limit_backoff_s(retries, self._rate_limit_cap_s)
                        self._log.warning(
                            "Rate limited (attempt %d/%d); waiting %.0fs before retry.",
                            retries,
                            self._max_rate_limit_retries,
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
