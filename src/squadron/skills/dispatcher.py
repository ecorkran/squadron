"""Read the skill names a dispatcher command declares.

A dispatcher (``/sq:analysis``, ``$sq-analysis``) lists the skills it routes
to on a ``Valid skills:`` line. The dispatcher drift test and the capability
probe both read that line through ``dispatcher_skills``.
"""

import re

_VALID_SKILLS_PREFIX = "valid skills:"
_BACKTICKED = re.compile(r"`([^`]+)`")


def dispatcher_skills(text: str) -> set[str] | None:
    """Return the backtick-quoted skill names on the first ``Valid skills:`` line.

    The match ignores case and leading whitespace; separators between names
    are ignored. Returns ``None`` when the text has no such line.
    """
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.casefold().startswith(_VALID_SKILLS_PREFIX):
            return set(_BACKTICKED.findall(stripped))
    return None
