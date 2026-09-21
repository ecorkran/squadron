"""Parse checkbox state out of a task file's markdown.

The first checkbox reader in the codebase. ``review.template_inputs._tasks_input``
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
