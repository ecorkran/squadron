"""Recognize the CLI's API-error reply so it is never taken for model output (issue #325).

When an API call fails (a usage limit, a bad login, a server error) the CLI reports it
as an assistant message from its ``<synthetic>`` placeholder model, with the failure
named in the typed ``error`` field and the CLI's notice as the text, e.g. "You've hit
your 5-hour limit · resets 11:20am". Classification reads the typed field only; the
text is carried into the exception for the operator.
"""

from __future__ import annotations

from claude_agent_sdk import AssistantMessage, TextBlock
from claude_agent_sdk.types import AssistantMessageError

from squadron.providers.errors import (
    ProviderAPIError,
    ProviderAuthError,
    ProviderError,
    ProviderRateLimitError,
)

#: The provider error each SDK ``AssistantMessageError`` value maps to. Anything not
#: listed (a value a newer SDK adds) is a generic API error.
_ERROR_TYPES: dict[AssistantMessageError, type[ProviderError]] = {
    "rate_limit": ProviderRateLimitError,
    "authentication_failed": ProviderAuthError,
}


def api_error_from_reply(message: AssistantMessage) -> ProviderError | None:
    """The provider error a top-level API-error reply stands for, or None for a real reply.

    A subagent's failed call (``parent_tool_use_id`` set) returns None: it reaches the
    parent model as a tool result and the parent decides what to do.
    """
    if message.error is None or message.parent_tool_use_id is not None:
        return None
    notice = " ".join(block.text for block in message.content if isinstance(block, TextBlock))
    detail = f"SDK returned an API error instead of a reply ({message.error}): {notice}"
    error_type = _ERROR_TYPES.get(message.error, ProviderAPIError)
    return error_type(detail)
