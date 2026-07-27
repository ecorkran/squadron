"""Shared exception hierarchy for all provider implementations."""

from __future__ import annotations


class ProviderError(Exception):
    """Base exception for all provider errors."""


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
