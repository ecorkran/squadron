"""Rendering project rules into prompt text."""

from __future__ import annotations

import re

from squadron.project_rules.selection import ProjectRules

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


_SECTION_HEADING = "## Project Rules"
_SEPARATOR = "\n\n---\n\n"


def render_project_rules(rules: ProjectRules) -> str:
    """A ``## Project Rules`` section: conventions (unless native), then each rule.

    Headings inside the files are demoted two levels so they sit under the
    section heading. Returns ``""`` when there is nothing to inject.
    """
    parts: list[str] = []
    if rules.conventions is not None and not rules.native:
        parts.append(demote_headings(rules.conventions.content.strip()))
    parts.extend(demote_headings(rule.content.strip()) for rule in rules.rules)
    if not parts:
        return ""
    return f"{_SECTION_HEADING}\n\n{_SEPARATOR.join(parts)}"
