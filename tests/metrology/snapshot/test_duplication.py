"""Token-window duplication detection, language-neutral (slice 401, D3)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from squadron.metrology.snapshot import duplication
from squadron.metrology.snapshot.duplication import (
    DUPLICATION_WINDOW_TOKENS,
    measure_duplication,
)
from squadron.metrology.snapshot_models import (
    AbsenceReason,
    Measurement,
    SourceLanguage,
    ToolIdentity,
)

TOOL = ToolIdentity(name="test-tokenizer", version="1", counting="c")
WIDTH = DUPLICATION_WINDOW_TOKENS
TOKENS_PER_LINE = 10


class FakeTokenError(ValueError):
    pass


def whitespace_tokens(_path: str, text: str) -> list[tuple[str, int]]:
    """Whitespace-separated words with their 1-based line; the word BAD raises."""
    tokens: list[tuple[str, int]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        for word in line.split():
            if word == "BAD":
                raise FakeTokenError("bad token")
            tokens.append((word, number))
    return tokens


def block(prefix: str, count: int = WIDTH) -> str:
    """*count* distinct tokens, ten to a line."""
    words = [f"{prefix}{i}" for i in range(count)]
    rows = [" ".join(words[i : i + TOKENS_PER_LINE]) for i in range(0, count, TOKENS_PER_LINE)]
    return "\n".join(rows) + "\n"


def run(
    repo: Path, files: dict[str, str], tokenizer: duplication.Tokenizer = whitespace_tokens
) -> Measurement:
    for name, content in files.items():
        (repo / name).write_text(content, encoding="utf-8")
    return measure_duplication(
        repo, list(files), SourceLanguage.PYTHON, TOOL, tokenizer, (FakeTokenError,)
    )


def test_shared_block_of_window_size_is_reported_in_both_files(tmp_path: Path) -> None:
    shared = block("s")

    measured = run(tmp_path, {"a.txt": shared + block("a"), "b.txt": block("b") + shared})

    assert measured.per_file == {"a.txt": 10, "b.txt": 10}
    assert measured.distribution is None


def test_block_one_token_short_is_not_reported(tmp_path: Path) -> None:
    shared = block("s", WIDTH - 1)

    measured = run(tmp_path, {"a.txt": shared, "b.txt": shared})

    assert measured.per_file == {}


def test_block_repeated_in_one_file_without_overlap_counts(tmp_path: Path) -> None:
    shared = block("s")

    measured = run(tmp_path, {"a.txt": shared + block("x") + shared})

    assert measured.per_file == {"a.txt": 20}


def test_run_of_one_repeated_token_with_overlapping_windows_does_not_count(tmp_path: Path) -> None:
    run_of_one_token = "\n".join(["same " * TOKENS_PER_LINE] * (WIDTH // TOKENS_PER_LINE + 5)) + "\n"

    measured = run(tmp_path, {"a.txt": run_of_one_token})

    assert measured.per_file == {}


def test_same_block_with_one_renamed_token_is_not_reported(tmp_path: Path) -> None:
    original = block("s")
    renamed = original.replace("s50", "renamed", 1)

    measured = run(tmp_path, {"a.txt": original, "b.txt": renamed})

    assert measured.per_file == {}


def test_files_without_duplication_are_absent_from_per_file(tmp_path: Path) -> None:
    shared = block("s")

    measured = run(tmp_path, {"a.txt": shared, "b.txt": shared, "c.txt": block("c")})

    assert set(measured.per_file) == {"a.txt", "b.txt"}


def test_distinct_windows_with_colliding_hashes_are_not_clones(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        duplication,
        "_window_hashes",
        lambda ids: [0] * max(len(ids) - WIDTH + 1, 0),
    )

    measured = run(tmp_path, {"a.txt": block("a"), "b.txt": block("b")})

    assert measured.per_file == {}


def test_token_count_past_the_ceiling_is_tool_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(duplication, "DUPLICATION_MAX_TOKENS", WIDTH + 5)

    with caplog.at_level(logging.WARNING):
        measured = run(tmp_path, {"a.txt": block("a"), "b.txt": block("b")})

    assert measured.absent is AbsenceReason.TOOL_FAILED
    assert measured.absent_detail == f"{2 * WIDTH} tokens passed the ceiling of {WIDTH + 5}"
    assert str(2 * WIDTH) in caplog.text
    assert str(WIDTH + 5) in caplog.text


def test_memory_error_in_the_tokenizer_is_tool_failed(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    def exhausted(_path: str, _text: str) -> list[tuple[str, int]]:
        raise MemoryError

    with caplog.at_level(logging.WARNING):
        measured = run(tmp_path, {"a.txt": block("a")}, exhausted)

    assert measured.absent is AbsenceReason.TOOL_FAILED
    assert "out of memory" in caplog.text


def test_tokenizer_error_and_unreadable_file_leave_the_other_files_compared(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    shared = block("s")

    with caplog.at_level(logging.WARNING):
        measured = run(tmp_path, {"a.txt": shared, "b.txt": shared, "bad.txt": "BAD"})
        measured = measure_duplication(
            tmp_path,
            ["a.txt", "b.txt", "bad.txt", "missing.txt"],
            SourceLanguage.PYTHON,
            TOOL,
            whitespace_tokens,
            (FakeTokenError,),
        )

    assert measured.unparsed_files == ["bad.txt", "missing.txt"]
    assert measured.per_file == {"a.txt": 10, "b.txt": 10}
    assert "Can't tokenize bad.txt" in caplog.text
    assert "Can't read missing.txt" in caplog.text


def test_undecodable_bytes_are_unparsed_and_logged(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (tmp_path / "binary.txt").write_bytes(b"\xff\xfe\x00 not utf-8")

    with caplog.at_level(logging.WARNING):
        measured = measure_duplication(
            tmp_path,
            ["binary.txt"],
            SourceLanguage.PYTHON,
            TOOL,
            whitespace_tokens,
            (FakeTokenError,),
        )

    assert measured.unparsed_files == ["binary.txt"]
    assert "isn't valid UTF-8" in caplog.text
