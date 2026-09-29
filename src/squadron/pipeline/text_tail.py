"""The tail of an agent's final text, for logs and flags (slice 932 D6/D7)."""

from __future__ import annotations

from typing import Final

__all__ = ["FINAL_TEXT_TAIL_CHARS", "tail_text"]

FINAL_TEXT_TAIL_CHARS: Final = 400
_EMPTY_RESPONSE: Final = "(empty response)"
_TRUNCATION_MARK: Final = "…"


def tail_text(text: str) -> str:
    """Return the last ``FINAL_TEXT_TAIL_CHARS`` of ``text``, whitespace collapsed.

    Prefixes ``…`` when it truncated. Empty or whitespace-only input renders
    as ``(empty response)``.
    """
    collapsed = " ".join(text.split())
    if not collapsed:
        return _EMPTY_RESPONSE
    if len(collapsed) <= FINAL_TEXT_TAIL_CHARS:
        return collapsed
    return _TRUNCATION_MARK + collapsed[-FINAL_TEXT_TAIL_CHARS:]
