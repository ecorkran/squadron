"""``write_new_file``: exclusive create without ``force``, atomic replace with it."""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import IO
from unittest.mock import patch

import pytest

from squadron.core.file_write import write_new_file


class _FailingWrite:
    """Wraps a real binary handle but fails on write, as a full disk would."""

    def __init__(self, real: IO[bytes]) -> None:
        self._real = real

    def __enter__(self) -> _FailingWrite:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self._real.close()

    def write(self, data: bytes) -> int:
        raise OSError("disk full")


def test_creates_missing_parents_and_returns_the_path(tmp_path: Path) -> None:
    target = tmp_path / "a" / "b" / "x.yaml"

    assert write_new_file(target, b"one", force=False) == target
    assert target.read_bytes() == b"one"


def test_existing_target_without_force_raises_naming_the_path(tmp_path: Path) -> None:
    target = tmp_path / "x.yaml"
    target.write_bytes(b"original")

    with pytest.raises(FileExistsError) as exc_info:
        write_new_file(target, b"new", force=False)

    assert str(target) in str(exc_info.value)
    assert target.read_bytes() == b"original"


def test_force_replaces_the_content(tmp_path: Path) -> None:
    target = tmp_path / "x.yaml"
    target.write_bytes(b"original")

    write_new_file(target, b"new", force=True)

    assert target.read_bytes() == b"new"
    assert [p.name for p in tmp_path.iterdir()] == ["x.yaml"]


def test_write_failure_after_create_leaves_no_partial_file(tmp_path: Path) -> None:
    target = tmp_path / "x.yaml"

    real_open = Path.open

    def failing_open(self: Path, mode: str = "r", *args: object, **kwargs: object) -> _FailingWrite:
        return _FailingWrite(real_open(self, mode, *args, **kwargs))  # type: ignore[arg-type]

    with patch.object(Path, "open", failing_open), pytest.raises(OSError, match="disk full"):
        write_new_file(target, b"data", force=False)

    assert not target.exists()


def test_write_failure_with_force_keeps_the_original_and_no_temp_file(tmp_path: Path) -> None:
    target = tmp_path / "x.yaml"
    target.write_bytes(b"original")

    real_fdopen = os.fdopen

    def failing_fdopen(fd: int, mode: str) -> _FailingWrite:
        return _FailingWrite(real_fdopen(fd, mode))

    with (
        patch("squadron.core.file_write.os.fdopen", failing_fdopen),
        pytest.raises(OSError, match="disk full"),
    ):
        write_new_file(target, b"data", force=True)

    assert target.read_bytes() == b"original"
    assert [p.name for p in tmp_path.iterdir()] == ["x.yaml"]


def test_two_writers_racing_exactly_one_wins(tmp_path: Path) -> None:
    target = tmp_path / "x.yaml"
    barrier = threading.Barrier(2)
    outcomes: list[str] = []

    def attempt(label: bytes) -> None:
        barrier.wait()
        try:
            write_new_file(target, label, force=False)
            outcomes.append("won")
        except FileExistsError:
            outcomes.append("lost")

    threads = [threading.Thread(target=attempt, args=(name,)) for name in (b"a", b"b")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(outcomes) == ["lost", "won"]
    assert target.read_bytes() in (b"a", b"b")
