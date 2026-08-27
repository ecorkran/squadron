"""Tests for the write_file tool."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

import pytest

from squadron.tools import builtin, registry  # noqa: F401  # builtin registers on import
from squadron.tools.models import ToolExecutor


@pytest.fixture
def write_file(tmp_path: Path) -> ToolExecutor:
    return registry.materialize(["write_file"], tmp_path)["write_file"]


async def test_creates_file_and_missing_parent_directories(
    tmp_path: Path, write_file: ToolExecutor
) -> None:
    result = await write_file({"path": "notes/a.txt", "content": "hello"})

    assert result.is_error is False
    assert (tmp_path / "notes").is_dir()
    assert (tmp_path / "notes" / "a.txt").read_text() == "hello"
    assert "Created" in result.content
    assert "5 bytes" in result.content


async def test_overwrite_reports_overwritten_and_new_byte_count(
    tmp_path: Path, write_file: ToolExecutor
) -> None:
    await write_file({"path": "a.txt", "content": "hello"})

    result = await write_file({"path": "a.txt", "content": "goodbye!"})

    assert result.is_error is False
    assert "Overwrote" in result.content
    assert "8 bytes" in result.content
    assert (tmp_path / "a.txt").read_text() == "goodbye!"


async def test_relative_traversal_is_rejected_and_writes_nothing(
    tmp_path: Path, write_file: ToolExecutor
) -> None:
    escape = tmp_path.parent / "escape.txt"

    result = await write_file({"path": "../escape.txt", "content": "pwned"})

    assert result.is_error is True
    assert "../escape.txt" in result.content
    assert not escape.exists()


async def test_absolute_path_outside_the_jail_is_rejected_and_writes_nothing(
    tmp_path: Path, write_file: ToolExecutor
) -> None:
    outside = tmp_path.parent / "outside_write.txt"

    result = await write_file({"path": str(outside), "content": "pwned"})

    assert result.is_error is True
    assert str(outside) in result.content
    assert not outside.exists()


async def test_symlink_out_of_the_jail_is_rejected_and_writes_nothing(
    tmp_path: Path, write_file: ToolExecutor
) -> None:
    outside = tmp_path.parent / "outside_link_dir"
    outside.mkdir(exist_ok=True)
    (tmp_path / "link").symlink_to(outside)

    result = await write_file({"path": "link/pwned.txt", "content": "pwned"})

    assert result.is_error is True
    assert "link/pwned.txt" in result.content
    assert not (outside / "pwned.txt").exists()


async def test_existing_directory_as_path_is_an_error(tmp_path: Path, write_file: ToolExecutor) -> None:
    (tmp_path / "sub").mkdir()

    result = await write_file({"path": "sub", "content": "x"})

    assert result.is_error is True
    assert "directory" in result.content


async def test_jail_rejection_logs_at_warning(
    write_file: ToolExecutor, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger="squadron.tools.builtin"):
        await write_file({"path": "../escape.txt", "content": "pwned"})

    records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert records
    assert "../escape.txt" in records[0].getMessage()


async def test_directory_error_logs_at_info(
    tmp_path: Path, write_file: ToolExecutor, caplog: pytest.LogCaptureFixture
) -> None:
    (tmp_path / "sub").mkdir()
    caplog.set_level(logging.INFO, logger="squadron.tools.builtin")

    await write_file({"path": "sub", "content": "x"})

    records = [r for r in caplog.records if r.levelno == logging.INFO]
    assert records
    assert "directory" in records[0].getMessage()


async def test_fifo_is_refused_instead_of_hanging(tmp_path: Path, write_file: ToolExecutor) -> None:
    """Writing to a FIFO with no reader blocks uninterruptibly; refuse before opening."""
    os.mkfifo(tmp_path / "pipe")

    result = await asyncio.wait_for(write_file({"path": "pipe", "content": "x"}), timeout=10)

    assert result.is_error is True
    assert "not a regular file" in result.content
