"""Parse checkbox state out of a task file's markdown.

The first checkbox reader in the codebase. ``review.template_inputs._task_files``
passes task files to the review template as bare paths for injection; nothing
in the tree reads their checkbox state until this module.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Any indent, any bullet (-, *, +), a checkbox marker, then the item text.
# Leniently matches the project's real task-file formatting rather than one
# exact layout, per the project's parsing rules.
_CHECKBOX_RE = re.compile(r"^\s*[-*+]\s+\[( |x|X)\]\s*(.*?)\s*$")

# The word an agent writes under a task it cannot finish without the Project Manager
# (slice 947 D2). Uppercase only, so prose like "blocked by" never matches.
BLOCKED_MARKER = "BLOCKED"

# Reported for a marker written with no reason, so the pause message never reads ": .".
NO_REASON_GIVEN = "(no reason given)"

# Lenient prefix (any indent, `>` quote marks, a list bullet with an optional checkbox,
# `*`/`_` emphasis), the marker word, then a required `:` or dash (emphasis allowed around
# it) before the text. A bare space is not enough: a task titled "BLOCKED tasks cleanup"
# must not stop a run.
_BLOCKED_RE = re.compile(
    r"^\s*(?:>\s*)*(?:[-*+]\s+(?:\[[ xX]\]\s*)?)?[*_]*"
    + re.escape(BLOCKED_MARKER)
    + r"(?![A-Za-z0-9])[*_]*\s*[:—–-]+[*_]*\s*(.*?)\s*$"
)


@dataclass(frozen=True)
class TaskItems:
    """Checkbox items from a task file, grouped by state, in document order."""

    checked: tuple[str, ...]
    unchecked: tuple[str, ...]


def parse_task_items(text: str) -> TaskItems:
    """Parse every checkbox list item in *text*, regardless of indent depth.

    A checked parent with an unchecked child yields one of each — each item
    is attributed to its own state, not its parent's.
    """
    checked: list[str] = []
    unchecked: list[str] = []
    for line in text.splitlines():
        match = _CHECKBOX_RE.match(line)
        if match is None:
            continue
        marker, item_text = match.group(1), match.group(2)
        if marker in ("x", "X"):
            checked.append(item_text)
        else:
            unchecked.append(item_text)
    return TaskItems(checked=tuple(checked), unchecked=tuple(unchecked))


def parse_blocked_markers(text: str) -> tuple[str, ...]:
    """The text after each ``BLOCKED`` marker line in *text*, in file order.

    Matches the formatting agents actually write: a blockquote
    (``> BLOCKED: ...``), a list item or checkbox item, bold, or a plain line,
    with ``:`` or a dash after the word. A marker with no text after it yields
    ``NO_REASON_GIVEN``.
    """
    matches = (_BLOCKED_RE.match(line) for line in text.splitlines())
    return tuple(match.group(1) or NO_REASON_GIVEN for match in matches if match is not None)
