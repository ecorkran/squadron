"""The documents under review, read whole for the prompt (#382).

A document review's ``input`` and ``against`` files are its subject. They go into the
prompt in full for every provider and tool set: leaving the reading to the model let a
review report on a sample of the document and stop. No size limit applies to them. A document that is
missing or unreadable fails the review; it is never cut or skipped.
"""

from __future__ import annotations

import logging
from pathlib import Path

from squadron.review.template_inputs import FILE_INPUT_KEYS

_logger = logging.getLogger(__name__)

__all__ = ["NUMBERED_NOTE", "ReviewDocumentError", "number_lines", "read_review_documents"]

#: Said in the label of a numbered document, so the model knows what the prefix is.
NUMBERED_NOTE = "each line prefixed with its line number"


class ReviewDocumentError(Exception):
    """A document under review could not be put in the prompt whole."""


def _resolve(value: str, cwd: str) -> Path | None:
    """*value* as a file, relative to the process cwd or to the review's ``cwd`` input."""
    for candidate in (Path(value), Path(cwd) / value):
        if candidate.is_file():
            return candidate
    return None


def read_review_documents(inputs: dict[str, str]) -> list[tuple[str, Path, str]]:
    """``(key, path, text)`` for each ``input`` / ``against`` document the review names.

    Raises:
        ReviewDocumentError: a named document is not a file or cannot be read.
    """
    documents: list[tuple[str, Path, str]] = []
    for key in FILE_INPUT_KEYS:
        value = inputs.get(key)
        if value is None:
            continue
        path = _resolve(value, inputs.get("cwd", "."))
        if path is None:
            _logger.error("Review document '%s' is not a file: %s", key, value)
            raise ReviewDocumentError(f"review document '{key}' is not a file: {value}")
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            _logger.exception("Review document '%s' could not be read: %s", key, path)
            raise ReviewDocumentError(
                f"review document '{key}' could not be read: {path}: {exc}"
            ) from exc
        documents.append((key, path, text))
    return documents


def number_lines(text: str) -> str:
    """*text* with each line prefixed by its 1-based number and a tab.

    A reviewer cites ``path:line``. Without numbers in the prompt it opens the file again
    with a tool to find them, which puts the whole document in context twice.
    """
    lines = text.splitlines()
    width = len(str(len(lines)))
    return "\n".join(f"{number:>{width}}\t{line}" for number, line in enumerate(lines, 1))
