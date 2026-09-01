"""Tests for the list_files tool."""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.tools import builtin, limits, registry  # noqa: F401  # builtin registers on import
from squadron.tools.models import ToolExecutor


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """A small fixture tree: two top-level files, a subdirectory with one more."""
    (tmp_path / "a.py").write_text("alpha")
    (tmp_path / "b.txt").write_text("beta")
    nested = tmp_path / "sub"
    nested.mkdir()
    (nested / "c.py").write_text("gamma")
    return tmp_path


@pytest.fixture
def list_files(tmp_path: Path) -> ToolExecutor:
    return registry.materialize(["list_files"], tmp_path)["list_files"]


def _lines(content: str) -> list[str]:
    return [line for line in content.splitlines() if line]


async def test_lists_files_in_default_path(tree: Path, list_files: ToolExecutor) -> None:
    result = await list_files({})

    assert result.is_error is False
    assert _lines(result.content) == ["a.py", "b.txt", "sub/"]


async def test_pattern_filters_results(tree: Path, list_files: ToolExecutor) -> None:
    result = await list_files({"pattern": "*.py"})

    assert result.is_error is False
    assert _lines(result.content) == ["a.py"]


async def test_recursive_true_descends_subdirectories(tree: Path, list_files: ToolExecutor) -> None:
    result = await list_files({"pattern": "*.py", "recursive": True})

    assert result.is_error is False
    assert _lines(result.content) == ["a.py", "sub/c.py"]


async def test_recursive_false_default_stays_shallow(tree: Path, list_files: ToolExecutor) -> None:
    result = await list_files({"pattern": "*.py", "recursive": False})

    assert _lines(result.content) == ["a.py"]


async def test_directories_marked_with_trailing_slash(tree: Path, list_files: ToolExecutor) -> None:
    result = await list_files({})

    assert "sub/" in _lines(result.content)
    assert "sub" not in _lines(result.content)


async def test_subdirectory_path_lists_relative_to_jail_root(
    tree: Path, list_files: ToolExecutor
) -> None:
    result = await list_files({"path": "sub"})

    assert result.is_error is False
    assert _lines(result.content) == ["sub/c.py"]


async def test_path_escaping_jail_returns_error(tree: Path, list_files: ToolExecutor) -> None:
    result = await list_files({"path": "../escape"})

    assert result.is_error is True
    assert "../escape" in result.content


async def test_absolute_path_outside_the_jail_is_rejected(tree: Path, list_files: ToolExecutor) -> None:
    outside = tree.parent

    result = await list_files({"path": str(outside)})

    assert result.is_error is True
    assert str(outside) in result.content


async def test_missing_path_returns_error(tree: Path, list_files: ToolExecutor) -> None:
    result = await list_files({"path": "nope"})

    assert result.is_error is True
    assert "does not exist" in result.content


async def test_file_path_returns_error(tree: Path, list_files: ToolExecutor) -> None:
    result = await list_files({"path": "a.py"})

    assert result.is_error is True
    assert "not a directory" in result.content


async def test_non_string_path_returns_error(tree: Path, list_files: ToolExecutor) -> None:
    result = await list_files({"path": 7})

    assert result.is_error is True
    assert "must be a string" in result.content


async def test_output_truncated_beyond_limit(
    tree: Path, list_files: ToolExecutor, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(limits, "MAX_OUTPUT_BYTES", 5)

    result = await list_files({})

    assert result.is_error is False
    assert "[truncated: listing is" in result.content
