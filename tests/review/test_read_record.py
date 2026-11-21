"""The record of what a review was given and what it opened (#382)."""

from __future__ import annotations

from pathlib import Path

import yaml

from squadron.core.tool_calls import (
    MAX_ARGUMENT_CHARS,
    ToolCallRecord,
    compact_arguments,
    files_read,
    searches_run,
)
from squadron.review.injected_file import injected_file
from squadron.review.read_record import read_record_dict, read_record_lines

CALLS = [
    ToolCallRecord("read_file", {"path": "src/a.py"}),
    ToolCallRecord("grep", {"pattern": "def run", "path": "src"}),
    ToolCallRecord("read_file", {"paths": ["src/b.py", "src/a.py"]}),
    ToolCallRecord("read_file", {"file_path": "src/missing.py"}, failed=True),
    ToolCallRecord("list_files", {"pattern": "*.md"}),
]


def test_files_read_lists_each_opened_path_once_and_skips_failed_reads() -> None:
    assert files_read(CALLS) == ["src/a.py", "src/b.py"]


def test_searches_are_listed_in_call_order() -> None:
    assert searches_run(CALLS) == ["grep def run in src", "list_files *.md in ."]


def test_long_arguments_are_cut() -> None:
    compacted = compact_arguments({"pattern": "x" * (MAX_ARGUMENT_CHARS + 50), "limit": 20})
    assert len(str(compacted["pattern"])) == MAX_ARGUMENT_CHARS + 1
    assert compacted["limit"] == 20


def _parse(lines: list[str]) -> dict[str, object]:
    return yaml.safe_load("\n".join(lines))


def test_frontmatter_lists_injected_files_reads_and_searches(tmp_path: Path) -> None:
    document = tmp_path / "docs" / 'ta"sks.md'
    injected = [injected_file("input", str(document), "body", injected_chars=4)]
    parsed = _parse(read_record_lines(injected, CALLS, str(tmp_path)))
    assert parsed["injected"] == [
        {
            "key": "input",
            "path": 'docs/ta"sks.md',
            "chars": 4,
            "sha256": injected[0].sha256,
            "whole": True,
        }
    ]
    assert parsed["filesRead"] == ["src/a.py", "src/b.py"]
    assert parsed["searches"] == ["grep def run in src", "list_files *.md in ."]


def test_no_tool_record_is_reported_as_unreported_not_as_empty() -> None:
    parsed = _parse(read_record_lines([], None, "."))
    assert parsed == {"injected": [], "readRecord": "unreported"}
    assert read_record_dict([], None, ".") == {"injected": [], "read_record": "unreported"}


def test_a_record_with_no_calls_is_empty_lists() -> None:
    parsed = _parse(read_record_lines(None, [], "."))
    assert parsed == {"filesRead": [], "searches": []}


def test_a_hand_built_result_adds_no_lines() -> None:
    assert read_record_lines(None, None, ".") == []
