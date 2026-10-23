"""Content hashes of tool config, for rule-set identity (D2, D8).

A rule set is identified by the config actually read. Whole config files are hashed by
content. A pyproject table is hashed as canonical JSON (sorted keys) rather than hashing
the whole file: squadron bumps ``version`` in ``pyproject.toml`` on every release, and
hashing the file would flag every release's lint and type counts as a rule-set change.
"""

from __future__ import annotations

import hashlib
import json
import tomllib
from collections.abc import Sequence
from pathlib import Path


def file_content_hash(path: Path) -> str:
    """SHA-256 of a file's bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pyproject_table_hash(pyproject: Path, table: Sequence[str]) -> str | None:
    """SHA-256 of one pyproject table as canonical JSON; None when the table is absent.

    Raises ``ValueError`` when the file can't be parsed as TOML.
    """
    try:
        document = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"{pyproject.name} is not valid TOML: {exc}") from exc
    node: object = document
    for key in table:
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]  # pyright: ignore[reportUnknownVariableType]
    canonical = json.dumps(node, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
