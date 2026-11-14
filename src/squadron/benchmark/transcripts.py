"""Agent-runtime transcripts: the tool calls a producer made (slice 424 D6).

Each runtime that dispatches a producer writes its own transcript under the scrubbed
``HOME`` (the D6 gate, Task 13 spike). A ``TranscriptSource`` reads those files and returns
the tool calls, whatever the runtime's file layout. Only the leak scan consumes the result.

Parsers are lenient on structure but loud on loss: a line or file that cannot be read is
recorded in ``problems`` and never skipped silently. Sources are registered per profile; a
profile with no source returns ``None`` and the caller decides to refuse the plan.
"""

from __future__ import annotations

import importlib
import json
import logging
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, cast

from squadron.providers.base import ProfileName

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ToolCall:
    """One tool call the agent made.

    ``input`` keeps the runtime's field names, except that a shell command is always
    ``input["command"]`` so the leak rules read one name for every runtime.
    """

    tool: str
    input: Mapping[str, object]


@dataclass(frozen=True)
class TranscriptResult:
    tool_calls: tuple[ToolCall, ...]
    files_read: int
    problems: tuple[str, ...] = field(default=())


class TranscriptSource(Protocol):
    def read(self, home: Path) -> TranscriptResult:
        """Every tool call recorded under the scrubbed *home*."""
        ...


def as_mapping(value: object) -> Mapping[str, object] | None:
    """*value* as a string-keyed mapping when it is a JSON object, else ``None``."""
    if not isinstance(value, dict):
        return None
    return {str(key): item for key, item in cast("dict[object, object]", value).items()}


def as_list(value: object) -> list[object] | None:
    """*value* as a list when it is a JSON array, else ``None``."""
    return list(cast("list[object]", value)) if isinstance(value, list) else None


def iter_jsonl(path: Path, problems: list[str]) -> Iterator[Mapping[str, object]]:
    """JSON-object lines of *path*; blank lines are skipped, bad lines go to *problems*."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        problems.append(f"{path}: cannot read ({exc})")
        return
    # Split on "\n" only: ``str.splitlines`` also splits on U+2028, U+0085, form feed and
    # others, which JSON allows unescaped inside a string, so a valid line would be cut.
    for number, line in enumerate(text.split("\n"), start=1):
        if not line.strip():
            continue
        try:
            entry: object = json.loads(line)
        except json.JSONDecodeError as exc:
            problems.append(f"{path}:{number}: not JSON ({exc.msg})")
            continue
        mapping = as_mapping(entry)
        if mapping is None:
            problems.append(f"{path}:{number}: not a JSON object")
            continue
        yield mapping


def sorted_files(directory: Path, pattern: str) -> list[Path]:
    """Files under *directory* matching *pattern*, recursively, in sorted path order."""
    return sorted(directory.rglob(pattern)) if directory.is_dir() else []


_REGISTRY: dict[ProfileName, TranscriptSource] = {}


def register_transcript_source(profile: ProfileName, source: TranscriptSource) -> None:
    """Make *source* the reader for *profile*."""
    _REGISTRY[profile] = source


def transcript_source_for(profile: ProfileName) -> TranscriptSource | None:
    """The source registered for *profile*, ``None`` when there is none."""
    _register_builtin_sources()
    return _REGISTRY.get(profile)


_BUILTIN_SOURCE_MODULES = (
    "squadron.benchmark.transcript_claude",
    "squadron.benchmark.transcript_codex",
)


def _register_builtin_sources() -> None:
    # The parser modules register themselves on import; importing here (not at module top)
    # avoids a cycle, and means a lookup never depends on who imported what first.
    for module_name in _BUILTIN_SOURCE_MODULES:
        importlib.import_module(module_name)
