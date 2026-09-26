"""Model-id equivalence — does an answering id count as the requested one?

Lives next to aliases.py because it is about model ids, not reviews.
"""

from __future__ import annotations

import re

_SNAPSHOT_SUFFIX = re.compile(r"-(\d{8}|\d{4}-\d{2}-\d{2})$")


def answers_as_requested(requested: str, answered: str) -> bool:
    """True iff ``answered`` counts as the model that was requested (D9).

    True when ``answered`` is exactly ``requested``, or ``requested`` plus a
    dated snapshot suffix (``-YYYYMMDD`` or ``-YYYY-MM-DD``). Everything else,
    including a same-family variant like ``gpt-5-mini`` for ``gpt-5``, is a
    substitution. Deliberately exact rather than guessed wider — see slice
    927 D9.
    """
    if answered == requested:
        return True
    if not answered.startswith(requested + "-"):
        return False
    suffix = answered[len(requested) :]
    return bool(_SNAPSHOT_SUFFIX.fullmatch(suffix))
