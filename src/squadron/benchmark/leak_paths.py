"""Path collection and the path rule of the leak scan (slice 424 D7).

Paths are read from tool inputs only, and judged lexically: a path is normalized
(``..`` folded) but never resolved against the filesystem, so a symlink inside the sandbox
(``.venv/bin/python``) does not count as a path outside it. Roots are matched in every
form ``path_forms`` produced.

Known limits, shared with the rest of the scan (see ``leak_scan``): paths built at run
time and file access inside scripts the model writes are not seen. ``~`` is read as the
user's real home, deliberately: inside the sandbox ``~`` is the scrubbed home, but a model
reaching for ``~/.ssh`` is reaching for the user's files, and the design calls it a hit.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path, PurePosixPath

from squadron.benchmark.leak_rules import LeakRules
from squadron.benchmark.leak_shell import command_tokens
from squadron.benchmark.transcripts import ToolCall

COMMAND_FIELD = "command"
#: File-tool input fields whose value is a path.
PATH_FIELDS = ("file_path", "path", "notebook_path")
#: ``pattern`` is a path only for these tools, and only when it starts like one.
PATTERN_FIELD = "pattern"
PATTERN_TOOLS = ("Glob", "Grep")
HOME_PREFIX = "~"
PARENT = ".."


def _candidates(token: str) -> Iterator[str]:
    yield token
    if "=" in token:
        # --git-dir=/x, --file=/etc/passwd, dd if=~/.ssh/id_rsa, GIT_DIR=/x
        yield token.split("=", 1)[1]


def resolve_in_tree(value: str, rules: LeakRules) -> Path:
    """The normalized absolute path *value* names: ``~`` is the real home, relative is in the tree."""
    if value.startswith("/"):
        return Path(os.path.normpath(value))
    if value == HOME_PREFIX or value.startswith(f"{HOME_PREFIX}/"):
        return Path(os.path.normpath(rules.real_home / value[2:]))
    return Path(os.path.normpath(rules.tree / value))


def _as_path(candidate: str, rules: LeakRules) -> Path | None:
    """The path *candidate* names when it is one we judge, else ``None``.

    Plain relative tokens (``src/a.py``) are not judged: they stay in the tree. A relative
    token is judged only when it climbs (``..``).
    """
    judged = (
        candidate.startswith("/")
        or candidate == HOME_PREFIX
        or candidate.startswith(f"{HOME_PREFIX}/")
        or PARENT in PurePosixPath(candidate).parts
    )
    return resolve_in_tree(candidate, rules) if judged else None


def is_under(path: Path, roots: tuple[Path, ...]) -> bool:
    return any(path == root or root in path.parents for root in roots)


def is_leaked_path(path: Path, rules: LeakRules) -> bool:
    """Under the user's home, checkout, install location or uv cache, and outside the sandbox.

    A path the producer's confinement covers is not a leak: the read was denied.
    """
    return is_under(path, rules.protected_roots) and not is_under(
        path, (*rules.sandbox_roots, *rules.confined_roots)
    )


def _field_values(call: ToolCall) -> Iterator[str]:
    for field_name in PATH_FIELDS:
        value = call.input.get(field_name)
        if isinstance(value, str):
            yield value
    pattern = call.input.get(PATTERN_FIELD)
    if (
        call.tool in PATTERN_TOOLS
        and isinstance(pattern, str)
        and pattern.startswith(("/", HOME_PREFIX))
    ):
        yield pattern


def collected_paths(call: ToolCall, rules: LeakRules) -> list[Path]:
    """Every path the call's file-tool fields and shell command name, normalized."""
    candidates = list(_field_values(call))
    command = call.input.get(COMMAND_FIELD)
    if isinstance(command, str):
        candidates.extend(c for token in command_tokens(command) for c in _candidates(token))
    paths = (_as_path(candidate, rules) for candidate in candidates)
    return [path for path in paths if path is not None]


def path_hits(call: ToolCall, rules: LeakRules) -> list[str]:
    """The offending paths of *call* under the path rule, in call order."""
    return [str(path) for path in collected_paths(call, rules) if is_leaked_path(path, rules)]
