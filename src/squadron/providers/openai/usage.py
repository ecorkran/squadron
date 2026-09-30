"""Reading token usage off OpenAI-shaped stream chunks (slice 931 D8, D12).

With ``stream_options={"include_usage": True}`` a backend sends usage on one chunk near the
end of the stream: OpenAI and Ollama on a chunk with no choices, OpenRouter on a chunk with
one empty choice. The SDK builds response models without validation, so a backend that
sends a string count or a list where a details object belongs reaches us as-is. A bad
accounting frame must not fail a review that produced its answer, so every field is read
defensively: a malformed one becomes ``None`` with a WARNING, and its siblings are kept.
"""

from __future__ import annotations

from openai.types.chat import ChatCompletionChunk

from squadron.core.usage import TokenUsage
from squadron.logging import get_logger

_log = get_logger("squadron.providers.openai.usage")

#: Shapes a backend has no business sending where a usage details object belongs.
_NOT_A_DETAILS_OBJECT = (str, bytes, int, float, list, tuple)


def read_chunk_usage(
    chunk: ChatCompletionChunk, *, warned: set[str] | None = None
) -> TokenUsage | None:
    """Return the chunk's token usage, or ``None`` when the chunk carries none.

    ``warned`` makes malformed-field WARNINGs once per caller-defined scope: a field
    already in the set is not logged again, and a newly logged field is added. With no
    set, every malformed field seen is logged.
    """
    usage: object = getattr(chunk, "usage", None)
    if usage is None:
        return None
    return TokenUsage(
        prompt=_count(usage, "prompt_tokens", "prompt_tokens", warned),
        cached=_detail_count(usage, "prompt_tokens_details", "cached_tokens", warned),
        completion=_count(usage, "completion_tokens", "completion_tokens", warned),
        reasoning=_detail_count(usage, "completion_tokens_details", "reasoning_tokens", warned),
    )


def _detail_count(
    usage: object, details_attr: str, count_attr: str, warned: set[str] | None
) -> int | None:
    """Read ``usage.<details_attr>.<count_attr>``; ``None`` when absent or malformed."""
    details: object = getattr(usage, details_attr, None)
    if details is None:
        return None
    if isinstance(details, _NOT_A_DETAILS_OBJECT):
        # A scalar or sequence where an object belongs: the whole details frame is
        # unreadable, so the count under it is too.
        _warn(f"{details_attr}.{count_attr}", getattr(usage, details_attr), warned)
        return None
    return _count(details, count_attr, f"{details_attr}.{count_attr}", warned)


def _count(source: object, attr: str, field_name: str, warned: set[str] | None) -> int | None:
    """Read one integer count; ``None`` when absent, WARNING and ``None`` when not an int."""
    value: object = getattr(source, attr, None)
    if value is None:
        return None
    # bool is an int subclass and is never a token count.
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    _warn(field_name, value, warned)
    return None


def _warn(field_name: str, value: object, warned: set[str] | None) -> None:
    if warned is not None:
        if field_name in warned:
            return
        warned.add(field_name)
    _log.warning(
        "Backend sent malformed token usage field %s: %.200r; recording it as not reported",
        field_name,
        value,
    )
