"""Tests for the read_file tool."""

from __future__ import annotations

import asyncio
import logging
import os
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


async def test_fifo_is_refused_instead_of_hanging(tmp_path: Path, read_file: ToolExecutor) -> None:
    """A FIFO inside the jail must not block the thread pool forever.

    ``asyncio.to_thread`` workers cannot be cancelled, so an uninterruptible open() here would
    hang the process even against a caller-side timeout. The tool refuses before opening.
    """
    os.mkfifo(tmp_path / "pipe")

    result = await asyncio.wait_for(read_file({"path": "pipe"}), timeout=10)

    assert result.is_error is True
    assert "not a regular file" in result.content


async def test_special_file_refusal_logs_at_info(
    tmp_path: Path, read_file: ToolExecutor, caplog: pytest.LogCaptureFixture
) -> None:
    os.mkfifo(tmp_path / "pipe")
    caplog.set_level(logging.INFO, logger="squadron.tools.builtin")

    await asyncio.wait_for(read_file({"path": "pipe"}), timeout=10)

    records = [r for r in caplog.records if r.levelno == logging.INFO]
    assert records
    assert "not a regular file" in records[0].getMessage()


# --- Trailing line references in the path -----------------------------------------------


@pytest.mark.parametrize("suffix", [":1050", ":10-20", ":12:5", "#L12", "#L12-L40"])
async def test_trailing_line_reference_reads_the_file(
    tmp_path: Path, read_file: ToolExecutor, suffix: str
) -> None:
    """Models pass a citation such as `ConsistencyChecker.ts:1050` as the path (seen live in
    a glm-5.3-flash review). The file exists; the citation is not part of its name."""
    target = tmp_path / "src" / "ConsistencyChecker.ts"
    target.parent.mkdir()
    target.write_text("export class ConsistencyChecker {}\n")

    result = await read_file({"path": f"{target}{suffix}"})

    assert result.is_error is False
    assert "export class ConsistencyChecker {}" in result.content
    assert f"'{target}{suffix}' does not exist" in result.content


async def test_a_real_file_with_a_colon_name_is_read_as_named(
    tmp_path: Path, read_file: ToolExecutor
) -> None:
    """The literal path wins when it exists; stripping only applies to a miss."""
    (tmp_path / "a.txt").write_text("the plain file")
    (tmp_path / "a.txt:12").write_text("the colon file")

    result = await read_file({"path": "a.txt:12"})

    assert result.content == "the colon file"


async def test_line_reference_on_a_missing_file_is_still_not_found(read_file: ToolExecutor) -> None:
    result = await read_file({"path": "nope.ts:12"})

    assert result.is_error is True
    assert "not found" in result.content


async def test_line_reference_cannot_escape_the_jail(tmp_path: Path, read_file: ToolExecutor) -> None:
    outside = tmp_path.parent / "outside-ref.txt"
    outside.write_text("secret")

    result = await read_file({"path": f"{outside}:3"})

    assert result.is_error is True
    assert "secret" not in result.content
