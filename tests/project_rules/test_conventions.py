"""Tests for conventions-file discovery (D2)."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

from squadron.project_rules.conventions import (
    ConventionsReadError,
    ConventionsSource,
    find_conventions,
)

_AGENTS = ConventionsSource.AGENTS_MD
_CLAUDE = ConventionsSource.CLAUDE_MD
_DOT = ConventionsSource.DOT_CLAUDE_CLAUDE_MD


def _write(root: Path, source: ConventionsSource) -> None:
    path = root / source.value
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"conventions from {source.value}")


@pytest.mark.parametrize(
    ("present", "chosen", "skipped"),
    [
        ([_AGENTS], _AGENTS, []),
        ([_CLAUDE], _CLAUDE, []),
        ([_DOT], _DOT, []),
        ([_AGENTS, _CLAUDE], _AGENTS, [_CLAUDE]),
        ([_AGENTS, _CLAUDE, _DOT], _AGENTS, [_CLAUDE, _DOT]),
    ],
)
def test_choice_and_skipped(
    tmp_path: Path,
    present: list[ConventionsSource],
    chosen: ConventionsSource,
    skipped: list[ConventionsSource],
) -> None:
    for source in present:
        _write(tmp_path, source)
    lookup = find_conventions(tmp_path)
    assert lookup.chosen is not None
    assert lookup.chosen.source is chosen
    assert lookup.chosen.content == f"conventions from {chosen.value}"
    assert lookup.skipped == skipped


def test_none_present(tmp_path: Path) -> None:
    lookup = find_conventions(tmp_path)
    assert lookup.chosen is None
    assert lookup.skipped == []


def test_import_lines_left_as_written(tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").write_text("@AGENTS.md\nNotes\n")
    lookup = find_conventions(tmp_path)
    assert lookup.chosen is not None
    assert lookup.chosen.content == "@AGENTS.md\nNotes\n"


def test_broken_symlink_raises_and_does_not_fall_through(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").symlink_to(tmp_path / "missing.md")
    _write(tmp_path, _CLAUDE)
    with pytest.raises(ConventionsReadError, match="AGENTS.md"):
        find_conventions(tmp_path)


@pytest.mark.skipif(
    sys.platform == "win32" or os.geteuid() == 0, reason="chmod 000 is readable by root"
)
def test_unreadable_file_raises(tmp_path: Path) -> None:
    _write(tmp_path, _AGENTS)
    _write(tmp_path, _CLAUDE)
    agents = tmp_path / "AGENTS.md"
    agents.chmod(0)
    try:
        with pytest.raises(ConventionsReadError, match=re.escape(str(agents))):
            find_conventions(tmp_path)
    finally:
        agents.chmod(0o644)
