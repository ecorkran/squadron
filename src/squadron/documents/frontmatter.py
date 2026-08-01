"""Lenient YAML frontmatter read/update helpers.

Leniency is modeled on ``metrology.identity.read_review_frontmatter``: tolerate
a BOM and leading blank lines before the opening ``---`` fence, split on the
closing ``---``, and ``yaml.safe_load`` the block.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import yaml


class FrontmatterError(Exception):
    """Raised when a document's YAML frontmatter block is malformed or absent."""


def _split_document(text: str) -> tuple[str, str, str] | None:
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
    split = _split_document(text)
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


def update_frontmatter(path: Path, fields: dict[str, object]) -> None:
    """Merge ``fields`` into the frontmatter block of ``path``.

    Existing key order is preserved; new keys are appended to the end of the
    block. The document body is preserved byte-for-byte.

    Raises:
        FrontmatterError: the file has no frontmatter block, the block is not
            closed, or it does not parse to a YAML mapping.
    """
    text = path.read_text(encoding="utf-8")
    split = _split_document(text)
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

    dumped = yaml.safe_dump(merged, sort_keys=False, default_flow_style=False, allow_unicode=True)
    path.write_text(f"{leading}---\n{dumped}---{body}", encoding="utf-8")
