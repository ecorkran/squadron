"""Tests for the grep tool, including its bounded-matching guarantee."""

from __future__ import annotations

import logging
import time
from pathlib import Path

import pytest

from squadron.tools import builtin, limits, registry  # noqa: F401  # builtin registers on import
from squadron.tools.models import ToolExecutor


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """A small fixture tree with matches spread across two file types and a subdirectory."""
    (tmp_path / "a.py").write_text("import os\nneedle here\n")
    (tmp_path / "b.txt").write_text("no match\nneedle also here\n")
    nested = tmp_path / "sub"
    nested.mkdir()
    (nested / "c.py").write_text("needle nested\n")
    return tmp_path


@pytest.fixture
def grep(tmp_path: Path) -> ToolExecutor:
    return registry.materialize(["grep"], tmp_path)["grep"]


def _lines(content: str) -> list[str]:
    return [line for line in content.splitlines() if line]


async def test_matches_pattern_across_files(tree: Path, grep: ToolExecutor) -> None:
    result = await grep({"pattern": "needle"})

    assert result.is_error is False
    assert _lines(result.content) == [
        "a.py:2:needle here",
        "b.txt:2:needle also here",
        "sub/c.py:1:needle nested",
    ]


async def test_glob_filters_files_searched(tree: Path, grep: ToolExecutor) -> None:
    result = await grep({"pattern": "needle", "glob": "*.txt"})

    assert _lines(result.content) == ["b.txt:2:needle also here"]


async def test_max_results_caps_output(tree: Path, grep: ToolExecutor) -> None:
    result = await grep({"pattern": "needle", "max_results": 2})

    assert len(_lines(result.content)) == 2


async def test_path_narrows_search_to_subdirectory(tree: Path, grep: ToolExecutor) -> None:
    result = await grep({"pattern": "needle", "path": "sub"})

    assert _lines(result.content) == ["sub/c.py:1:needle nested"]


async def test_single_file_path_is_searched_directly(tree: Path, grep: ToolExecutor) -> None:
    result = await grep({"pattern": "needle", "path": "a.py"})

    assert _lines(result.content) == ["a.py:2:needle here"]


async def test_no_matches_returns_empty_content(tree: Path, grep: ToolExecutor) -> None:
    result = await grep({"pattern": "zzz-absent"})

    assert result.is_error is False
    assert result.content == ""


async def test_path_escaping_jail_returns_error(tree: Path, grep: ToolExecutor) -> None:
    result = await grep({"pattern": "needle", "path": "../escape"})

    assert result.is_error is True
    assert "../escape" in result.content


async def test_invalid_regex_returns_error_not_raise(tree: Path, grep: ToolExecutor) -> None:
    result = await grep({"pattern": "([a-"})

    assert result.is_error is True
    assert "invalid regular expression" in result.content


async def test_missing_pattern_returns_error(tree: Path, grep: ToolExecutor) -> None:
    result = await grep({})

    assert result.is_error is True
    assert "pattern" in result.content


async def test_boolean_max_results_rejected(tree: Path, grep: ToolExecutor) -> None:
    result = await grep({"pattern": "needle", "max_results": True})

    assert result.is_error is True
    assert "must be an integer" in result.content


async def test_output_truncated_beyond_limit(
    tree: Path, grep: ToolExecutor, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(limits, "MAX_OUTPUT_BYTES", 5)

    result = await grep({"pattern": "needle"})

    assert result.is_error is False
    assert "[truncated: matches is" in result.content


async def test_pathological_pattern_times_out(
    tmp_path: Path,
    grep: ToolExecutor,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Direct regression test for design decision D9.

    The rejected ``asyncio.wait_for`` approach measured 72.8s against a 1.0s timeout because a
    thread running the regex engine cannot be cancelled from outside. The ``regex`` package's
    engine-level ``timeout=`` bounds the search from within, so the call must return close to
    the budget rather than run to completion.
    """
    monkeypatch.setattr(limits, "GREP_TIMEOUT_S", 0.5)
    # A long non-matching run of 'a's: (a|a)* has exponentially many ways to split it, and the
    # trailing '$' forces the engine to try them all before failing.
    (tmp_path / "bad.txt").write_text("a" * 400 + "b")

    with caplog.at_level(logging.WARNING, logger="squadron.tools.builtin"):
        started = time.monotonic()
        result = await grep({"pattern": r"(a|a)*$", "glob": "bad.txt"})
        elapsed = time.monotonic() - started

    assert result.is_error is True
    assert "exceeded" in result.content
    # Returns near the budget, not after running the search to completion.
    assert elapsed < limits.GREP_TIMEOUT_S * 4
    assert any(r"(a|a)*$" in record.getMessage() for record in caplog.records)
