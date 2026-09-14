"""Tests for intersect_files_with_range (slice 382, design D7).

A PR review's --files narrows within the PR's own range rather than replacing it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.review.git_utils import EmptyScopeCase, EmptyScopeError
from squadron.review.scope import intersect_files_with_range


def _touch(cwd: Path, *relative_paths: str) -> None:
    for rel in relative_paths:
        path = cwd / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x")


def test_glob_matching_some_changed_paths_returns_only_the_intersection(tmp_path: Path) -> None:
    _touch(tmp_path, "src/a.py", "src/b.py", "docs/readme.md")
    changed_paths = ["src/a.py", "src/b.py", "docs/readme.md"]

    result = intersect_files_with_range("src/*.py", changed_paths, str(tmp_path))

    assert result == ["src/a.py", "src/b.py"]


def test_glob_matching_nothing_in_range_raises_naming_glob_and_range(tmp_path: Path) -> None:
    _touch(tmp_path, "src/a.py", "docs/readme.md")
    changed_paths = ["src/a.py", "docs/readme.md"]

    with pytest.raises(EmptyScopeError) as excinfo:
        intersect_files_with_range("vendor/*.py", changed_paths, str(tmp_path))

    assert excinfo.value.case == EmptyScopeCase.GLOB_MATCHED_NOTHING_IN_RANGE
    assert "vendor/*.py" in str(excinfo.value)
    assert "2" in str(excinfo.value)  # names the range size


def test_glob_matching_everything_in_range_returns_full_list_unchanged(tmp_path: Path) -> None:
    _touch(tmp_path, "src/a.py", "src/b.py")
    changed_paths = ["src/a.py", "src/b.py"]

    result = intersect_files_with_range("src/*.py", changed_paths, str(tmp_path))

    assert result == changed_paths


def test_intersection_preserves_changed_paths_order(tmp_path: Path) -> None:
    """Order matches the range's own order, not the glob's arbitrary filesystem order."""
    _touch(tmp_path, "src/z.py", "src/a.py", "src/m.py")
    changed_paths = ["src/z.py", "src/a.py", "src/m.py"]

    result = intersect_files_with_range("src/*.py", changed_paths, str(tmp_path))

    assert result == ["src/z.py", "src/a.py", "src/m.py"]
