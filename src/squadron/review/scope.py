"""Narrowing a review's scope within an already-resolved range.

Distinct from ``rules.py`` (rules-file discovery and content loading): this module
resolves *which files* a review covers, not which conventions apply to them.
"""

from __future__ import annotations

import glob as glob_mod
import logging
from collections.abc import Sequence
from pathlib import Path

from squadron.review.git_utils import EmptyScopeCase, EmptyScopeError

_logger = logging.getLogger(__name__)


def intersect_files_with_range(files_glob: str, changed_paths: Sequence[str], cwd: str) -> list[str]:
    """Narrow *changed_paths* to those also matched by *files_glob*.

    slice 382, design D7: a PR review's ``--files`` scopes down within the PR's own diff
    range rather than replacing it — the range is already known from the fetched
    ``FetchedRange.changed_paths``, so this never issues a second git call.

    Raises :class:`EmptyScopeError` when the glob matches none of *changed_paths* — a
    scoping flag that excludes the entire range is very likely a typo or the wrong
    pattern, not an instruction to review nothing (same rationale as the other
    ``EmptyScopeError`` cases: refusing pre-flight costs nothing and says why).
    """
    matched = set(glob_mod.glob(files_glob, root_dir=Path(cwd)))
    intersection = [path for path in changed_paths if path in matched]

    if not intersection:
        _logger.warning(
            "'--files %r' matched none of the %d changed file(s) in range for cwd=%r.",
            files_glob,
            len(changed_paths),
            cwd,
        )
        raise EmptyScopeError(
            f"'--files {files_glob!r}' matched none of the {len(changed_paths)} changed "
            "file(s) in this pull request's range. Check the glob, or omit --files to "
            "review the whole range.",
            case=EmptyScopeCase.GLOB_MATCHED_NOTHING_IN_RANGE,
        )

    return intersection
