"""Shared helpers for rendering compaction instructions with pipeline params.

Used by the ``compact`` pipeline action and the ``summary_render`` module
so that missing placeholders render as literal ``{name}`` text rather than
raising ``KeyError``.
"""

from __future__ import annotations


class LenientDict(dict[str, object]):
    """Dict that returns the placeholder itself for missing keys.

    Prevents ``KeyError`` when a template references a param that isn't
    present (e.g. ``{slice}`` when no slice param was given).
    """

    def __missing__(self, key: str) -> str:
        return f"{{{key}}}"


def render_with_params(instructions: str, params: dict[str, object]) -> str:
    """Render ``instructions`` by substituting ``{name}`` placeholders.

    Missing placeholders are preserved as literal text (via ``LenientDict``).
    """
    return instructions.format_map(LenientDict(params))
