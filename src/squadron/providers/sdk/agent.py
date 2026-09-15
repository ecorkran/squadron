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
    RateLimitEvent,
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
    RATE_LIMIT_MAX_BACKOFF_S,
    RateLimitRejected,
    RateLimitStats,
    event_blocks,
    is_throttle,
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
        # Cumulative across the agent's life, so a caller can report what a
        # run actually cost in throttling rather than leaving it anecdotal.
        self._rate_limit_stats = RateLimitStats()

    # -- Protocol properties ------------------------------------------------

    @property
    def name(self) -> str:
        return self._name

    @property
    def agent_type(self) -> str:
        return "sdk"

    @property
    def rate_limit_stats(self) -> RateLimitStats:
        """Throttling absorbed so far, for the caller's run summary."""
        return self._rate_limit_stats

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
        """Yield SDK messages, handling two distinct concerns.

        1. **An unparseable message.** The bundled CLI can emit a message
           type newer than the installed SDK's parser knows. The parser
           raises ``MessageParseError``, which terminates the SDK's
           generator permanently — the next ``__anext__`` raises
           ``StopAsyncIteration``. There is nothing to resume; the skip
           below just ends iteration cleanly (WARNING, then return) instead
           of propagating an exception over a message that carried nothing
           the caller needed.
        2. **A typed ``RateLimitEvent``.** The stream stays alive when one
           arrives — it parses like any other message. A ``rejected``
           status is a genuine throttle: this raises ``RateLimitRejected``,
           which the caller's retry loop catches via ``is_throttle``. An
           informational status (``allowed``/``allowed_warning``) is logged
           at DEBUG and yielded through unchanged, reaching translation the
           same way any other message type does — it must not be dropped.

        Connection errors, process failures, and every other
        ``ClaudeSDKError`` propagate untouched.
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
            if isinstance(sdk_msg, RateLimitEvent):
                if event_blocks(sdk_msg):
                    raise RateLimitRejected(
                        f"rate_limit_event status={sdk_msg.rate_limit_info.status!r}"
                    )
                self._log.debug(
                    "Informational rate-limit event (%s); passing through.",
                    sdk_msg.rate_limit_info.status,
                )
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
                if is_throttle(exc) and retries < self._max_rate_limit_retries:
                    retries += 1
                    delay = rate_limit_backoff_s(retries, self._rate_limit_cap_s)
                    self._log.warning(
                        "Rate limited (attempt %d/%d); waiting %.0fs before retry.",
                        retries,
                        self._max_rate_limit_retries,
                        delay,
                    )
                    self._rate_limit_stats.record(delay)
                    await asyncio.sleep(delay)
                    continue
                self._state = AgentState.failed
                if is_throttle(exc):
                    raise ProviderRateLimitError(str(exc)) from exc
                raise ProviderError(str(exc)) from exc

    async def _handle_client_mode(self, message: Message) -> AsyncIterator[Message]:
        """Multi-turn execution via ``ClaudeSDKClient``.

        Includes rate-limit retry logic: a ``rejected`` ``RateLimitEvent``
        raises ``RateLimitRejected`` (see ``_skip_unparseable``). We wait an
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
                    if is_throttle(exc) and retries < self._max_rate_limit_retries:
                        retries += 1
                        delay = rate_limit_backoff_s(retries, self._rate_limit_cap_s)
                        self._log.warning(
                            "Rate limited (attempt %d/%d); waiting %.0fs before retry.",
                            retries,
                            self._max_rate_limit_retries,
                            delay,
                        )
                        self._rate_limit_stats.record(delay)
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
            except Exception:  # noqa: BLE001
                # Teardown boundary: disconnect() closes the Claude Agent
                # SDK's subprocess/transport, whose failure modes are
                # internal to the SDK and not enumerable here. A cleanup
                # failure at shutdown must not block finishing teardown —
                # logged for diagnosability, never re-raised.
                self._log.exception("SDKAgent.shutdown: ignoring error during client disconnect")
            self._client = None
        self._state = AgentState.terminated
