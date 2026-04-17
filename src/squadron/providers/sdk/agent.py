"""ClaudeSDKAgent — wraps claude-agent-sdk for task execution."""

from __future__ import annotations

from collections.abc import AsyncIterator

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

from squadron.core.models import AgentState, Message
from squadron.logging import get_logger
from squadron.providers.errors import (
    ProviderAPIError,
    ProviderAuthError,
    ProviderError,
)
from squadron.providers.sdk.translation import translate_sdk_message

_MAX_RATE_LIMIT_RETRIES = 10


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

    async def _handle_query_mode(self, message: Message) -> AsyncIterator[Message]:
        """One-shot execution via ``sdk_query``.

        Retries the full query when a ``rate_limit_event`` surfaces as a
        ``ClaudeSDKError`` — the CLI handles the backoff delay, so retrying
        the query is safe.
        """
        self._state = AgentState.processing
        retries = 0
        while True:
            try:
                async for sdk_msg in sdk_query(
                    prompt=message.content, options=self._options
                ):
                    for translated in translate_sdk_message(sdk_msg, sender=self._name):
                        yield translated
                self._state = AgentState.idle
                return
            except CLINotFoundError as exc:
                self._state = AgentState.failed
                raise ProviderAuthError(str(exc)) from exc
            except ProcessError as exc:
                self._state = AgentState.failed
                raise ProviderAPIError(
                    str(exc), status_code=getattr(exc, "exit_code", None)
                ) from exc
            except ClaudeSDKError as exc:
                if "rate_limit_event" in str(exc) and retries < _MAX_RATE_LIMIT_RETRIES:
                    retries += 1
                    self._log.debug(
                        "Rate limit event %d/%d (retrying query)",
                        retries,
                        _MAX_RATE_LIMIT_RETRIES,
                    )
                    continue
                self._state = AgentState.failed
                raise ProviderError(str(exc)) from exc

    async def _handle_client_mode(self, message: Message) -> AsyncIterator[Message]:
        """Multi-turn execution via ``ClaudeSDKClient``.

        Includes rate-limit retry logic: when the CLI emits a
        ``rate_limit_event`` the SDK raises ``ClaudeSDKError``.
        We restart ``receive_response()`` on the same session
        (the underlying channel remains intact) up to
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
                    async for sdk_msg in self._client.receive_response():
                        for translated in translate_sdk_message(
                            sdk_msg, sender=self._name
                        ):
                            yield translated
                    break  # normal completion
                except ClaudeSDKError as exc:
                    if (
                        "rate_limit_event" in str(exc)
                        and retries < _MAX_RATE_LIMIT_RETRIES
                    ):
                        retries += 1
                        self._log.debug(
                            "Rate limit event %d/%d (CLI handles backoff)",
                            retries,
                            _MAX_RATE_LIMIT_RETRIES,
                        )
                        continue
                    raise
            self._state = AgentState.idle
        except CLINotFoundError as exc:
            self._state = AgentState.failed
            raise ProviderAuthError(str(exc)) from exc
        except ProcessError as exc:
            self._state = AgentState.failed
            raise ProviderAPIError(
                str(exc), status_code=getattr(exc, "exit_code", None)
            ) from exc
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
