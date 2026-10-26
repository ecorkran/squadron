"""Tests for finding the newest comprehension doc (slice 440 D3)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from squadron.onboard.comprehension import (
    ANALYSIS_DIR,
    COMPREHENSION_SUFFIX,
    newest_comprehension,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _write(root: Path, name: str) -> Path:
    path = root / ANALYSIS_DIR / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("doc")
    return path


def test_no_analysis_directory_returns_none(tmp_path: Path) -> None:
    assert newest_comprehension(tmp_path) is None


def test_empty_analysis_directory_returns_none(tmp_path: Path) -> None:
    (tmp_path / ANALYSIS_DIR).mkdir(parents=True)
    assert newest_comprehension(tmp_path) is None


def test_other_analysis_docs_are_ignored(tmp_path: Path) -> None:
    _write(tmp_path, "940-analysis.tech-debt-audit.md")
    assert newest_comprehension(tmp_path) is None


def test_highest_integer_index_wins_not_lexical(tmp_path: Path) -> None:
    _write(tmp_path, f"940{COMPREHENSION_SUFFIX}")
    newest = _write(tmp_path, f"1002{COMPREHENSION_SUFFIX}")
    assert newest_comprehension(tmp_path) == newest


def test_file_without_leading_index_is_skipped_with_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _write(tmp_path, f"notes{COMPREHENSION_SUFFIX}")
    with caplog.at_level(logging.WARNING):
        result = newest_comprehension(tmp_path)
    assert result is None
    assert any(
        record.levelno == logging.WARNING and f"notes{COMPREHENSION_SUFFIX}" in record.getMessage()
        for record in caplog.records
    )


def test_understand_command_names_the_same_path() -> None:
    command = (_REPO_ROOT / "commands" / "analysis" / "understand.md").read_text(encoding="utf-8")
    assert f"{ANALYSIS_DIR}/{{index}}{COMPREHENSION_SUFFIX}" in command
