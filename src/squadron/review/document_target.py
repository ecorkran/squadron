"""The slice a review's input path names, by the file-naming convention (issue #142).

``104-slice.findings-verdicts-and-provenance.md`` carries its slice index in its name.
A review given that path saves exactly as one given ``104`` would, but only when
Context Forge lists that file under that index; the slice is never guessed.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path

from squadron.review.persistence import SliceInfo


class DocumentKind(StrEnum):
    """The slice documents a review can be given by path."""

    SLICE = "slice"
    TASKS = "tasks"


_NAME_PATTERNS: dict[DocumentKind, re.Pattern[str]] = {
    DocumentKind.SLICE: re.compile(r"^(\d+)-slice\..+\.md$"),
    DocumentKind.TASKS: re.compile(r"^(\d+)-tasks\..+\.md$"),
}


class DocumentNotListedError(ValueError):
    """A conventional name whose index Context Forge resolves, but not to this file."""


def _listed_names(info: SliceInfo, kind: DocumentKind) -> set[str]:
    if kind is DocumentKind.SLICE:
        return {Path(info["design_file"]).name} if info["design_file"] else set()
    return {Path(name).name for name in info["task_files"]}


def slice_for_document(
    path: str, kind: DocumentKind, resolve: Callable[[int], SliceInfo]
) -> SliceInfo | None:
    """The slice ``path`` belongs to, or None when its name does not follow the convention.

    ``resolve`` maps an index to Context Forge's record and raises when it cannot.

    Raises:
        DocumentNotListedError: the name carries an index whose slice does not list
            this file as its document.
    """
    name = Path(path).name
    match = _NAME_PATTERNS[kind].match(name)
    if match is None:
        return None
    info = resolve(int(match.group(1)))
    if name not in _listed_names(info, kind):
        raise DocumentNotListedError(
            f"{name} is not slice {info['index']}'s {kind} document in Context Forge"
        )
    return info
