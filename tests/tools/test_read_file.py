"""Tests for the read_file tool."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from squadron.tools import builtin, limits, registry  # noqa: F401  # builtin registers on import
from squadron.tools.models import ToolExecutor


@pytest.fixture
def read_file(tmp_path: Path) -> ToolExecutor:
    return registry.materialize(["read_file"], tmp_path)["read_file"]


async def test_reads_a_file_in_the_jail(tmp_path: Path, read_file: ToolExecutor) -> None:
    (tmp_path / "a.txt").write_text("hello")

    result = await read_file({"path": "a.txt"})

    assert result.is_error is False
    assert result.content == "hello"


async def test_absolute_path_inside_the_jail_succeeds(tmp_path: Path, read_file: ToolExecutor) -> None:
    target = tmp_path / "a.txt"
    target.write_text("hello")

    result = await read_file({"path": str(target)})

    assert result.is_error is False
    assert result.content == "hello"


async def test_relative_traversal_is_rejected(read_file: ToolExecutor) -> None:
    result = await read_file({"path": "../escape.txt"})

    assert result.is_error is True
    assert "../escape.txt" in result.content


async def test_absolute_path_outside_the_jail_is_rejected(
    tmp_path: Path, read_file: ToolExecutor
) -> None:
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("secret")

    result = await read_file({"path": str(outside)})

    assert result.is_error is True
    assert str(outside) in result.content


async def test_symlink_out_of_the_jail_is_rejected(tmp_path: Path, read_file: ToolExecutor) -> None:
    outside = tmp_path.parent / "outside_dir"
    outside.mkdir(exist_ok=True)
    (outside / "secret.txt").write_text("secret-contents")
    (tmp_path / "link").symlink_to(outside)

    result = await read_file({"path": "link/secret.txt"})

    assert result.is_error is True
    assert "link/secret.txt" in result.content
    # The file contents must not leak through the rejection message.
    assert "secret-contents" not in result.content


async def test_oversized_content_is_truncated_with_a_visible_marker(
    tmp_path: Path, read_file: ToolExecutor, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(limits, "MAX_READ_BYTES", 10)
    (tmp_path / "big.txt").write_text("x" * 100)

    result = await read_file({"path": "big.txt"})

    assert result.is_error is False
    assert result.content.startswith("x" * 10)
    assert "truncated" in result.content
    assert "100 bytes" in result.content


async def test_missing_file_is_an_error(read_file: ToolExecutor) -> None:
    result = await read_file({"path": "nope.txt"})

    assert result.is_error is True
    assert "not found" in result.content


async def test_directory_as_path_is_an_error(tmp_path: Path, read_file: ToolExecutor) -> None:
    (tmp_path / "sub").mkdir()

    result = await read_file({"path": "sub"})

    assert result.is_error is True
    assert "directory" in result.content


async def test_jail_rejection_logs_at_warning(
    read_file: ToolExecutor, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger="squadron.tools.builtin"):
        await read_file({"path": "../escape.txt"})

    records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert records
    assert "../escape.txt" in records[0].getMessage()


async def test_missing_file_logs_at_info(
    read_file: ToolExecutor, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="squadron.tools.builtin")

    await read_file({"path": "nope.txt"})

    records = [r for r in caplog.records if r.levelno == logging.INFO]
    assert records
    assert "not found" in records[0].getMessage()
