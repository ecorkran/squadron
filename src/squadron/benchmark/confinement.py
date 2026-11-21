"""Confine a benchmark producer's Claude Code session to its sandbox.

A scrubbed ``HOME`` does not stop a model that types an absolute path: it read the
operator's real ``~/.config/squadron`` and could read the real repository, which holds
the reference implementation. These settings make Claude Code refuse it at two layers:
the OS sandbox denies Bash commands (scripts included) any read under the real home but
the sandbox's own paths, and the file tools refuse reads and writes outside the working
directory. The sandbox cannot be bypassed (``allowUnsandboxedCommands: false``) and a
missing sandbox fails the command (``failIfUnavailable``) rather than running it free.

The settings reach the producer through ``pipeline.claude_settings`` in the sandbox
home's user config, which the producer's ``sq`` reads because its ``HOME`` is that home.
Non-SDK producers ignore the key.
"""

from __future__ import annotations

import json
import os
import tomllib
from collections.abc import Iterable
from pathlib import Path

import tomli_w

CLAUDE_SETTINGS_KEY = "pipeline.claude_settings"
_USER_CONFIG = Path(".config") / "squadron" / "config.toml"


#: More symlinks than this while resolving one path is a loop.
_MAX_SYMLINK_HOPS = 40


class SymlinkLoopError(Exception):
    """A toolchain path does not resolve: its symlinks loop."""


def toolchain_paths(entry_points: Iterable[Path], real_home: Path) -> list[Path]:
    """What the sandbox must let commands read for *entry_points* that live under *real_home*.

    Running a linked tool reads every symlink on the way to it (fnm's per-shell folder links
    to an alias, which links to the install) and then its install: ``<root>/bin/node``,
    or ``<root>/lib/.../index.js`` beside the interpreter. So each symlink met under
    *real_home* is listed, and the resolved file's install root: two levels up from a file
    in ``bin``, else its directory.
    """
    paths: list[Path] = []
    for entry in entry_points:
        resolved = Path(os.path.realpath(entry))
        root = resolved.parent.parent if resolved.parent.name == "bin" else resolved.parent
        for path in [*_symlinks_on(entry), root]:
            if path.is_relative_to(real_home) and path not in paths:
                paths.append(path)
    return paths


def _symlinks_on(path: Path) -> list[Path]:
    """Every symlink met while resolving absolute *path*, one component at a time."""
    found: list[Path] = []
    current = Path(path.anchor)
    pending = list(path.parts[1:])
    while pending:
        candidate = Path(os.path.normpath(current / pending.pop(0)))
        if not candidate.is_symlink():
            current = candidate
            continue
        found.append(candidate)
        if len(found) > _MAX_SYMLINK_HOPS:
            raise SymlinkLoopError(f"{path} does not resolve: more than {_MAX_SYMLINK_HOPS} links")
        target = Path(os.readlink(candidate))
        target = target if target.is_absolute() else candidate.parent / target
        current = Path(target.anchor)
        pending = list(target.parts[1:]) + pending
    return found


def confinement_settings(*, real_home: Path, tree: Path, home: Path, readable: Iterable[Path]) -> str:
    """The settings JSON: no reads under *real_home* except the sandbox and *readable*."""
    allowed = [str(tree), str(home), *(str(path) for path in readable)]
    settings = {
        "sandbox": {
            "enabled": True,
            "failIfUnavailable": True,
            "allowUnsandboxedCommands": False,
            "filesystem": {
                "denyRead": [str(real_home)],
                "allowRead": allowed,
                "allowWrite": [str(home)],
            },
        },
        "permissions": {
            "blockReadsOutsideWorkingDirectories": True,
            "blockWritesOutsideWorkingDirectories": True,
        },
    }
    return json.dumps(settings, separators=(",", ":"))


def write_confinement(home: Path, settings: str) -> None:
    """Set ``pipeline.claude_settings`` in the sandbox home's user config, keeping the rest."""
    path = home / _USER_CONFIG
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, object] = {}
    if path.is_file():
        with path.open("rb") as handle:
            existing = dict(tomllib.load(handle))
    if existing.get(CLAUDE_SETTINGS_KEY) == settings:
        return  # a second producer_env call leaves the home untouched
    existing[CLAUDE_SETTINGS_KEY] = settings
    with path.open("wb") as handle:
        tomli_w.dump(existing, handle)
