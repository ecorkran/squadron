"""What a review was given and what it opened, as frontmatter and JSON (#382).

``injected`` lists every input file whose text was put in the prompt, with its size and
hash. ``filesRead`` and ``searches`` list what the model did with its tools. When the
provider reported no tool-call record, ``readRecord: unreported`` says so; nothing is
inferred from a count.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from squadron.core.tool_calls import ToolCallRecord, files_read, searches_run
from squadron.review.injected_file import InjectedFile

__all__ = ["READ_RECORD_UNREPORTED", "read_record_dict", "read_record_lines"]

#: Value of ``readRecord`` when the provider stamped no tool-call record.
READ_RECORD_UNREPORTED = "unreported"


def _relative(path: str, cwd: str) -> str:
    """*path* relative to *cwd* when it is under it, so an artifact reads the same anywhere."""
    try:
        return str(Path(path).resolve().relative_to(Path(cwd).resolve()))
    except ValueError:
        # Not under cwd: an absolute path elsewhere, or already relative to another root.
        return path


def read_record_dict(
    injected: Sequence[InjectedFile] | None,
    tool_calls: Sequence[ToolCallRecord] | None,
    cwd: str,
) -> dict[str, object]:
    """The record as plain data: ``injected``, then ``files_read`` and ``searches`` or
    ``read_record: unreported``."""
    record: dict[str, object] = {}
    if injected is not None:
        record["injected"] = [
            {
                "key": item.key,
                "path": _relative(item.path, cwd),
                "chars": item.chars,
                "sha256": item.sha256,
                "whole": item.whole,
            }
            for item in injected
        ]
    if tool_calls is None:
        record["read_record"] = READ_RECORD_UNREPORTED
        return record
    record["files_read"] = [_relative(path, cwd) for path in files_read(tool_calls)]
    record["searches"] = searches_run(tool_calls)
    return record


def _string_list(key: str, values: Sequence[str]) -> list[str]:
    if not values:
        return [f"{key}: []"]
    # A JSON string is a valid YAML double-quoted scalar, escapes included.
    return [f"{key}:", *(f"  - {json.dumps(value)}" for value in values)]


def read_record_lines(
    injected: Sequence[InjectedFile] | None,
    tool_calls: Sequence[ToolCallRecord] | None,
    cwd: str,
) -> list[str]:
    """Frontmatter lines for the record; empty for a result that carries neither part."""
    if injected is None and tool_calls is None:
        return []
    lines: list[str] = []
    if injected:
        lines.append("injected:")
        for item in injected:
            lines += [
                f"  - key: {item.key}",
                f"    path: {json.dumps(_relative(item.path, cwd))}",
                f"    chars: {item.chars}",
                f"    sha256: {item.sha256}",
                f"    whole: {'true' if item.whole else 'false'}",
            ]
    elif injected is not None:
        lines.append("injected: []")
    if tool_calls is None:
        lines.append(f"readRecord: {READ_RECORD_UNREPORTED}")
        return lines
    lines += _string_list("filesRead", [_relative(p, cwd) for p in files_read(tool_calls)])
    lines += _string_list("searches", searches_run(tool_calls))
    return lines
