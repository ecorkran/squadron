"""Lenient YAML frontmatter read/update helpers.

Leniency is modeled on ``metrology.identity.read_review_frontmatter``: tolerate
a BOM and leading blank lines before the opening ``---`` fence, split on the
closing ``---``, and ``yaml.safe_load`` the block.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import yaml

from squadron.documents.schema import STATUS_ALIASES, DocumentStatus


class FrontmatterError(Exception):
    """Raised when a document's YAML frontmatter block is malformed or absent."""


def _validate_status_if_present(data: dict[str, object], *, context: str) -> None:
    """Raise if a top-level ``status`` key is present and not a valid value.

    Present-and-invalid only — never required. Machine artifacts legitimately
    omit ``status`` entirely, and a nested ``findingStatuses`` entry carries a
    ``FindingStatus``, not a document status, so only the top-level key is
    checked.
    """
    if "status" not in data:
        return
    status_value = str(data["status"])
    valid_values = {member.value for member in DocumentStatus} | set(STATUS_ALIASES)
    if status_value not in valid_values:
        accepted = ", ".join(member.value for member in DocumentStatus)
        raise FrontmatterError(
            f"Invalid status {status_value!r} in {context} — accepted values: {accepted}"
        )


def split_document(text: str) -> tuple[str, str, str] | None:
    """Split ``text`` into ``(leading, raw_frontmatter, body)``.

    ``leading`` is any BOM/blank-line prefix before the opening fence;
    ``raw_frontmatter`` is the unparsed block between the fences; ``body`` is
    everything after the closing fence, verbatim. Returns ``None`` when there
    is no opening fence or the block is never closed.
    """
    stripped = text.lstrip("﻿ \n")
    leading = text[: len(text) - len(stripped)]
    if not stripped.startswith("---"):
        return None
    parts = stripped.split("---", 2)
    if len(parts) < 3:
        return None
    _, raw_block, body = parts
    return leading, raw_block, body


def read_frontmatter(path: Path) -> dict[str, object] | None:
    """Parse the YAML frontmatter block of ``path``.

    Returns ``None`` when there is no block or it does not parse to a
    mapping — callers decide whether that absence is meaningful.
    """
    text = path.read_text(encoding="utf-8")
    split = split_document(text)
    if split is None:
        return None
    _, raw_block, _ = split
    try:
        loaded = yaml.safe_load(raw_block)
    except yaml.YAMLError:
        return None
    if not isinstance(loaded, dict):
        return None
    return {str(key): value for key, value in cast("dict[object, object]", loaded).items()}


#: Wide enough that safe_dump never folds a long value across lines. Folding is
#: valid YAML but makes an artifact harder to read and to grep.
FRONTMATTER_LINE_WIDTH = 4096


def yaml_safe(value: object) -> object:
    """Coerce a value to a type ``yaml.safe_dump`` can represent.

    The enums these artifacts carry (Verdict, Resolution, SettlingScreen,
    FindingStatus) are ``str`` subclasses, and SafeDumper dispatches on the
    exact type — an uncoerced member raises rather than serializing.
    """
    if value is None or isinstance(value, bool | int):
        return value
    return str(value)


def render_frontmatter_block(data: dict[str, object]) -> str:
    """The fenced YAML frontmatter block for *data*, without a trailing newline.

    Serialization goes through ``yaml.safe_dump``, never an f-string. These
    artifacts embed arbitrary model-authored text — a colon-space, a leading
    ``#`` or ``-``, or an embedded newline would corrupt a hand-rendered block,
    and the whole point of the block is that a machine can read it back.

    Raises:
        FrontmatterError: a top-level ``status`` key is present and not a
            valid ``DocumentStatus`` (or alias). Absent ``status`` is fine —
            machine artifacts legitimately have none.
    """
    _validate_status_if_present(data, context="frontmatter block")
    dumped = yaml.safe_dump(
        data,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        width=FRONTMATTER_LINE_WIDTH,
    )
    return f"---\n{dumped.rstrip(chr(10))}\n---"


def update_frontmatter(path: Path, fields: dict[str, object]) -> None:
    """Merge ``fields`` into the frontmatter block of ``path``.

    Existing key order is preserved; new keys are appended to the end of the
    block. The document body is preserved byte-for-byte.

    Raises:
        FrontmatterError: the file has no frontmatter block, the block is not
            closed, it does not parse to a YAML mapping, or the merged result
            carries a top-level ``status`` that is present and invalid.
    """
    text = path.read_text(encoding="utf-8")
    split = split_document(text)
    if split is None:
        raise FrontmatterError(f"No YAML frontmatter block found in {path}")
    leading, raw_block, body = split

    try:
        loaded = yaml.safe_load(raw_block)
    except yaml.YAMLError as exc:
        raise FrontmatterError(f"Frontmatter is not valid YAML in {path}: {exc}") from exc
    if not isinstance(loaded, dict):
        raise FrontmatterError(f"Frontmatter did not parse to a mapping in {path}")

    merged: dict[str, object] = {
        str(key): value for key, value in cast("dict[object, object]", loaded).items()
    }
    merged.update(fields)
    _validate_status_if_present(merged, context=str(path))

    dumped = yaml.safe_dump(merged, sort_keys=False, default_flow_style=False, allow_unicode=True)
    path.write_text(f"{leading}---\n{dumped}---{body}", encoding="utf-8")
