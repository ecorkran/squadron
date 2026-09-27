"""Shared exception hierarchy for all provider implementations."""

from __future__ import annotations


class ProviderError(Exception):
    """Base exception for all provider errors.

    ``tool_calls_made`` rides the error so a failure that produces no response
    can still be told apart from one that never had tools: "given tools, said
    nothing" and "ran without tools" look identical in an artifact otherwise
    (slice 265 D5). ``None`` means the raiser had no count to offer.
    """

    def __init__(self, *args: object, tool_calls_made: int | None = None) -> None:
        super().__init__(*args)
        self.tool_calls_made = tool_calls_made


class EmptyFinalTurnError(ProviderError):
    """The model ended its turn with no text and no tool calls.

    The turn's telemetry rides the error because ``collect_turn`` cannot fold it after a
    raise (slice 924 D7).
    """

    def __init__(
        self,
        message: str,
        *,
        finish_reason: str | None,
        reasoning_chars: int,
        tool_calls_made: int,
        failed_tool_calls: int,
    ) -> None:
        super().__init__(message, tool_calls_made=tool_calls_made)
        self.finish_reason = finish_reason
        self.reasoning_chars = reasoning_chars
        self.failed_tool_calls = failed_tool_calls


class ProviderAuthError(ProviderError):
    """Authentication or credential errors."""


class ProviderAPIError(ProviderError):
    """Errors from the underlying LLM API (rate limits, server errors, etc.)."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class ProviderRateLimitError(ProviderError):
    """The provider rate-limited the request and retries were exhausted.

    Distinct from a generic ``ProviderError`` so callers can tell "slow
    down and try later" from "this run was malformed". A long unattended
    campaign should pause on this rather than burning its remaining work
    on requests that will fail identically.
    """


class ProviderTimeoutError(ProviderError):
    """Request timeout errors."""
