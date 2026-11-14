"""The instruction files in effect for a producer replay (slice 424 D5).

The scrubbed home carries no user-level instructions (421 D7), so the files in the tree are
all the instructions the agent can see. Their paths and hashes go on the replay record, so a
result is never compared across different instructions without saying so.
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path

_logger = logging.getLogger(__name__)

INSTRUCTION_FILE_NAMES = frozenset({"CLAUDE.md", "AGENTS.md"})
RULES_DIRECTORY = (".claude", "rules")
#: Directories never searched: repository metadata and installed packages, which can hold
#: files with these names that no agent instruction is.
SKIPPED_DIRECTORIES = frozenset({".git", ".venv", "node_modules"})


def _is_instruction_file(relative: Path) -> bool:
    in_rules = relative.parts[: len(RULES_DIRECTORY)] == RULES_DIRECTORY
    return relative.name in INSTRUCTION_FILE_NAMES or (
        in_rules and len(relative.parts) > len(RULES_DIRECTORY)
    )


#: Recorded in place of a sha256 for a file that cannot be hashed as an instruction of the tree.
OUTSIDE_TREE_MARKER = "outside-tree"
UNREADABLE_MARKER = "unreadable"


def _digest(path: Path, tree_root: Path) -> str:
    """sha256 of the file's content, or a marker (after a WARNING) when it cannot be hashed:
    a symlink pointing outside the tree, or one that is dangling or unreadable. The file stays
    on the record so a result is never compared across instructions without saying so, and one
    such file does not abort the benchmark."""
    if not path.resolve().is_relative_to(tree_root):
        _logger.warning("instruction file %s points outside the tree; recorded as a marker", path)
        return OUTSIDE_TREE_MARKER
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:  # dangling link, a directory, or a permission problem
        _logger.warning("instruction file %s cannot be read (%s); recorded as a marker", path, exc)
        return UNREADABLE_MARKER


def instruction_files(tree: Path) -> tuple[tuple[str, str], ...]:
    """``(relative path, sha256)`` of every ``CLAUDE.md``, ``AGENTS.md`` and ``.claude/rules/**``
    file in *tree*, sorted by path. Call it before the producer runs, while the tree is still
    at the start commit. A file that cannot be hashed (a symlink out of the tree, a dangling or
    unreadable one) is logged at WARNING and listed with a marker in place of its hash."""
    found: list[tuple[str, str]] = []
    tree_root = tree.resolve()
    for directory, subdirectories, names in os.walk(tree):
        subdirectories[:] = [d for d in subdirectories if d not in SKIPPED_DIRECTORIES]
        for name in names:
            path = Path(directory) / name
            relative = path.relative_to(tree)
            if not _is_instruction_file(relative):
                continue
            found.append((relative.as_posix(), _digest(path, tree_root)))
    return tuple(sorted(found))
