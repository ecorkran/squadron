"""Parse the ``{index}-slice.{name}`` branch-name convention.

The reverse lookup (``_find_slice_branch`` in ``review.git_utils``) already
exists; this is the forward direction the tree lacks.
"""

from __future__ import annotations

import re

_SLICE_BRANCH_RE = re.compile(r"^(\d+)-slice\.(.+)$")


def parse_slice_branch(branch: str) -> int | None:
    """Return the slice index when *branch* matches ``{index}-slice.{name}``.

    A branch that does not match returns ``None``. That is not an error —
    the architecture says such a branch "gets a commits-only description,
    not a guessed slice."
    """
    match = _SLICE_BRANCH_RE.match(branch)
    if match is None:
        return None
    return int(match.group(1))
