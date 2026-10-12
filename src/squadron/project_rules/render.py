"""Rendering project rules into prompt text."""

from __future__ import annotations

import re

_HEADING_RE = re.compile(r"^(#{1,6})\s", re.MULTILINE)


def demote_headings(content: str, levels: int = 2) -> str:
    """Shift all markdown headings down by *levels* (e.g. H1→H3 when levels=2).

    Headings that would exceed H6 are clamped to H6.
    Lines that are not headings are returned unchanged.
    """

    def _shift(m: re.Match[str]) -> str:
        hashes = m.group(1)
        new_depth = min(len(hashes) + levels, 6)
        return "#" * new_depth + " "

    return _HEADING_RE.sub(_shift, content)
