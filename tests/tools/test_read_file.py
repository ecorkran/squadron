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


# --- Characterization: single-path output, byte for byte (slice 931 Task 12) ---
# Written against the pre-batch implementation and left unedited afterwards, so the helper
# extraction and the `paths` addition cannot change what a single `path` returns (D5).


@pytest.fixture
def characterization_tree(tmp_path: Path) -> Path:
    (tmp_path / "a.txt").write_text("hello\nworld\n")
    (tmp_path / "big.txt").write_bytes(b"x" * (limits.MAX_READ_BYTES + 10))
    (tmp_path / "sub").mkdir()
    os.mkfifo(tmp_path / "pipe")
    # Resolved here, not in the async test: error messages carry the resolved path.
    return tmp_path.resolve()


_WHOLE_FILE_NOTE = (
    "[read_file: '{requested}' does not exist; read 'a.txt' — the trailing line reference "
    "was ignored and the whole file follows]\nhello\nworld\n"
)


@pytest.mark.parametrize(
    ("path", "is_error", "expected"),
    [
        ("a.txt", False, "hello\nworld\n"),
        ("a.txt:12", False, _WHOLE_FILE_NOTE.format(requested="a.txt:12")),
        ("a.txt#L1-L2", False, _WHOLE_FILE_NOTE.format(requested="a.txt#L1-L2")),
        ("missing.txt", True, "Error: file not found: {tmp}/missing.txt"),
        (
            "../escape.txt",
            True,
            "Error: path '../escape.txt' resolves outside the working directory and was rejected.",
        ),
        ("pipe", True, "Error: path is not a regular file: pipe"),
        ("sub", True, "Error: path is a directory: {tmp}/sub"),
        (
            "big.txt",
            False,
            "x"
            * limits.MAX_READ_BYTES
            + f"\n[truncated: {{tmp}}/big.txt is {limits.MAX_READ_BYTES + 10} bytes, "
            f"showing first {limits.MAX_READ_BYTES}]",
        ),
    ],
    ids=[
        "normal",
        "line-ref",
        "anchor-ref",
        "missing",
        "jail-escape",
        "fifo",
        "directory",
        "truncated",
    ],
)
async def test_single_path_output_is_unchanged(
    characterization_tree: Path, path: str, is_error: bool, expected: str
) -> None:
    read = registry.materialize(["read_file"], characterization_tree)["read_file"]

    result = await read({"path": path})

    assert result.is_error is is_error
    assert result.content == expected.replace("{tmp}", str(characterization_tree))


# --- Batched reads: `paths` and the batch budget (slice 931 D5, D6, D12) ---

_BUDGET_MARKER = "[not read: batch budget of {budget} bytes reached; request it in another call]"


async def test_batch_returns_headed_sections_in_request_order(
    tmp_path: Path, read_file: ToolExecutor
) -> None:
    (tmp_path / "a.txt").write_text("A\n")
    (tmp_path / "b.txt").write_text("B")

    result = await read_file({"paths": ["b.txt", "a.txt"]})

    assert result.is_error is False
    assert result.content == "==> b.txt <==\nB\n\n==> a.txt <==\nA\n"


async def test_single_entry_paths_still_gets_a_header(tmp_path: Path, read_file: ToolExecutor) -> None:
    (tmp_path / "a.txt").write_text("A\n")

    result = await read_file({"paths": ["a.txt"]})

    assert result.content == "==> a.txt <==\nA\n"


async def test_mixed_failure_renders_inline_and_is_not_an_error(
    tmp_path: Path, read_file: ToolExecutor
) -> None:
    (tmp_path / "a.txt").write_text("A\n")

    result = await read_file({"paths": ["a.txt", "../escape.txt", "missing.txt"]})

    assert result.is_error is False
    sections = result.content.split("\n\n")
    assert sections[0] == "==> a.txt <==\nA"
    assert sections[1].startswith("==> ../escape.txt <==\nError: path '../escape.txt'")
    assert sections[2].startswith("==> missing.txt <==\nError: file not found:")


async def test_every_file_failing_is_an_error(read_file: ToolExecutor) -> None:
    result = await read_file({"paths": ["missing-1.txt", "missing-2.txt"]})

    assert result.is_error is True
    assert "==> missing-1.txt <==\nError:" in result.content
    assert "==> missing-2.txt <==\nError:" in result.content


async def test_budget_cutoff_marks_remaining_paths_and_warns(
    tmp_path: Path,
    read_file: ToolExecutor,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(limits, "MAX_READ_BATCH_BYTES", 10)
    for name in ("a.txt", "b.txt", "c.txt", "d.txt"):
        (tmp_path / name).write_text("12345\n")
    marker = _BUDGET_MARKER.format(budget=10)

    with caplog.at_level(logging.WARNING):
        result = await read_file({"paths": ["a.txt", "b.txt", "c.txt", "d.txt"]})

    assert result.content == (
        "==> a.txt <==\n12345\n\n"
        f"==> b.txt <==\n{marker}\n\n"
        f"==> c.txt <==\n{marker}\n\n"
        f"==> d.txt <==\n{marker}\n"
    )
    assert result.is_error is False
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings == ["read_file: batch budget of 10 bytes reached; 3 path(s) not read"]


async def test_oversize_first_file_is_read_with_normal_truncation(
    tmp_path: Path, read_file: ToolExecutor, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(limits, "MAX_READ_BYTES", 8)
    monkeypatch.setattr(limits, "MAX_READ_BATCH_BYTES", 8)
    (tmp_path / "big.txt").write_text("0123456789abcdef")
    (tmp_path / "small.txt").write_text("s")

    single = await read_file({"path": "big.txt"})
    batch = await read_file({"paths": ["big.txt", "small.txt"]})

    assert batch.content.startswith(f"==> big.txt <==\n{single.content}")
    assert "==> small.txt <==\n[not read: batch budget of 8 bytes" in batch.content


@pytest.mark.parametrize(
    "args",
    [{"path": "a.txt", "paths": ["a.txt"]}, {}, {"paths": []}, {"paths": "a.txt"}, {"paths": [1]}],
    ids=["both", "neither", "empty-paths", "paths-not-list", "paths-not-strings"],
)
async def test_malformed_path_arguments_are_errors_naming_the_rule(
    read_file: ToolExecutor, args: dict[str, object]
) -> None:
    result = await read_file(args)

    assert result.is_error is True
    assert "paths" in result.content
    assert "unexpected failure" not in result.content


def test_full_batch_stays_under_the_per_result_floor() -> None:
    """D6: raising a batch bound without the floor (or vice versa) fails here.

    The true worst case the executor allows: the byte budget spent, and every one of
    the most paths a call may name, each of the longest allowed length, carrying a
    header and a not-read marker.
    """
    path = "p" * limits.MAX_READ_PATH_CHARS
    marker = _BUDGET_MARKER.format(budget=limits.MAX_READ_BATCH_BYTES)
    per_path_overhead = len(f"==> {path} <==\n{marker}\n\n")

    batch_chars = limits.MAX_READ_BATCH_BYTES + limits.MAX_READ_BATCH_PATHS * per_path_overhead

    assert batch_chars < limits.min_tool_result_chars()


def test_registered_schema_offers_path_and_paths() -> None:
    descriptor = registry.lookup("read_file")
    assert descriptor is not None
    parameters = descriptor.parameters

    assert set(parameters["properties"]) == {"path", "paths"}  # type: ignore[index]
    assert parameters["required"] == []


async def test_too_many_paths_is_a_correctable_error(read_file: ToolExecutor) -> None:
    paths = [f"f{i}.txt" for i in range(limits.MAX_READ_BATCH_PATHS + 1)]

    result = await read_file({"paths": paths})

    assert result.is_error is True
    assert f"at most {limits.MAX_READ_BATCH_PATHS} per call" in result.content


async def test_overlong_path_in_a_batch_is_a_correctable_error(read_file: ToolExecutor) -> None:
    result = await read_file({"paths": ["a.txt", "p" * (limits.MAX_READ_PATH_CHARS + 1)]})

    assert result.is_error is True
    assert f"at most {limits.MAX_READ_PATH_CHARS} characters" in result.content
