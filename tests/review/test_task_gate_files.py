"""Tests for the task-file gate's read-and-gate entry point (slice 933)."""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.review.models import Verdict
from squadron.review.task_gate_files import TaskFileReadError, gate_task_files


def _inputs(path: Path) -> dict[str, str]:
    return {"input": str(path), "against": "design.md", "cwd": "."}


def test_clean_file_gives_no_results(tmp_path: Path) -> None:
    task_file = tmp_path / "clean.md"
    task_file.write_text("- [ ] Add the scanner\n", encoding="utf-8")
    assert gate_task_files([_inputs(task_file)]) == {}


def test_offending_file_gives_one_fail(tmp_path: Path) -> None:
    clean = tmp_path / "part-1.md"
    clean.write_text("- [ ] Add the scanner\n", encoding="utf-8")
    offending = tmp_path / "part-2.md"
    offending.write_text("- [ ] Merge to `main`.\n", encoding="utf-8")

    results = gate_task_files([_inputs(clean), _inputs(offending)])

    assert list(results) == [str(offending)]
    assert results[str(offending)].verdict is Verdict.FAIL


def test_undecodable_file_raises_with_path(tmp_path: Path) -> None:
    task_file = tmp_path / "bad.md"
    task_file.write_bytes(b"- [ ] \xff\xfe broken\n")
    with pytest.raises(TaskFileReadError, match="bad.md"):
        gate_task_files([_inputs(task_file)])
