"""The record of the tool calls a model made: proof of what it read (#382).

Both agents write one ``ToolCallRecord`` per call, in call order, under ``TOOL_CALLS_KEY``
on a call's final message. Tool names are the canonical squadron ones on every provider.
The helpers below answer the two questions an artifact records: which files were opened,
and which searches were run.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import cast

__all__ = [
    "FILES_READ_KEY",
    "SEARCHES_KEY",
    "TOOL_CALLS_KEY",
    "ToolCallRecord",
    "compact_arguments",
    "files_read",
    "read_summary",
    "searches_run",
]

#: Message-metadata key holding ``list[ToolCallRecord]``.
TOOL_CALLS_KEY = "tool_calls"

#: Run-state keys for the plain-data summary of a record (``read_summary``).
FILES_READ_KEY = "files_read"
SEARCHES_KEY = "searches"

#: Longest argument value kept; a search pattern or path longer than this is cut.
MAX_ARGUMENT_CHARS = 300

READ_TOOL = "read_file"
SEARCH_TOOLS = ("grep", "list_files")
#: Argument names that hold a path to read, across squadron's tools and Claude Code's.
_PATH_ARGUMENTS = ("path", "file_path")
_PATH_LIST_ARGUMENT = "paths"
_PATTERN_ARGUMENT = "pattern"


@dataclass
class ToolCallRecord:
    """One tool call: the canonical tool name, its arguments, and whether it failed."""

    tool: str
    arguments: dict[str, object] = field(default_factory=dict[str, object])
    failed: bool = False


def _compact(value: object) -> object:
    if isinstance(value, bool | int | float) or value is None:
        return value
    if isinstance(value, list):
        return [_compact(item) for item in cast(list[object], value)]
    text = value if isinstance(value, str) else str(value)
    return text if len(text) <= MAX_ARGUMENT_CHARS else text[:MAX_ARGUMENT_CHARS] + "…"


def compact_arguments(raw: Mapping[str, object] | None) -> dict[str, object]:
    """*raw* tool arguments with long strings cut, safe to store in an artifact."""
    if not raw:
        return {}
    return {str(key): _compact(value) for key, value in raw.items()}


def _paths(record: ToolCallRecord) -> list[str]:
    found = [str(record.arguments[name]) for name in _PATH_ARGUMENTS if record.arguments.get(name)]
    listed = record.arguments.get(_PATH_LIST_ARGUMENT)
    if isinstance(listed, list):
        found += [str(item) for item in cast(list[object], listed)]
    return found


def files_read(records: Iterable[ToolCallRecord]) -> list[str]:
    """Distinct paths opened by successful read calls, in first-read order."""
    seen: list[str] = []
    for record in records:
        if record.tool != READ_TOOL or record.failed:
            continue
        seen += [path for path in _paths(record) if path not in seen]
    return seen


def searches_run(records: Iterable[ToolCallRecord]) -> list[str]:
    """Each search call as ``tool pattern in path``, in call order."""
    lines: list[str] = []
    for record in records:
        if record.tool not in SEARCH_TOOLS:
            continue
        pattern = record.arguments.get(_PATTERN_ARGUMENT, "*")
        where = next(iter(_paths(record)), ".")
        lines.append(f"{record.tool} {pattern} in {where}")
    return lines


def read_summary(records: Iterable[ToolCallRecord]) -> dict[str, list[str]]:
    """Files opened and searches run, as plain lists a run state can store."""
    calls = list(records)
    return {FILES_READ_KEY: files_read(calls), SEARCHES_KEY: searches_run(calls)}
