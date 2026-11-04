"""The cross-platform file lock behind the run and git-metadata locks.

The real-lock tests run on whichever platform runs the suite: ``flock`` on POSIX,
``msvcrt.locking`` on Windows. The fake-module tests pin each platform's calls, so CI on
one platform still checks the other's branch.
"""

from __future__ import annotations

import errno
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import TextIO

import pytest

from squadron.core import file_lock


def _lock(path: Path) -> TextIO:
    """Open *path* and lock it; the caller closes the returned file."""
    lock_file = path.open("a")
    file_lock.lock_exclusive_nowait(lock_file)
    return lock_file


# ---------------------------------------------------------------------------
# Real lock on this platform
# ---------------------------------------------------------------------------


def test_a_second_open_is_refused_until_the_holder_unlocks(tmp_path: Path) -> None:
    lock_path = tmp_path / "x.flock"
    holder = _lock(lock_path)
    try:
        with lock_path.open("a") as rival:
            with pytest.raises(BlockingIOError):
                file_lock.lock_exclusive_nowait(rival)
            file_lock.unlock(holder)
            file_lock.lock_exclusive_nowait(rival)
            file_lock.unlock(rival)
    finally:
        holder.close()


def test_closing_the_holder_releases_the_lock(tmp_path: Path) -> None:
    lock_path = tmp_path / "x.flock"
    _lock(lock_path).close()

    _lock(lock_path).close()


def test_the_lock_leaves_the_file_empty(tmp_path: Path) -> None:
    lock_path = tmp_path / "x.flock"
    with _lock(lock_path):
        assert lock_path.stat().st_size == 0


def test_holders_contend_when_append_mode_opens_at_the_end_of_a_nonempty_file(
    tmp_path: Path,
) -> None:
    # Append mode opens at end of file; msvcrt locks from the current position, so every
    # holder must lock from offset 0 or two holders would lock different bytes.
    lock_path = tmp_path / "x.flock"
    lock_path.write_text("left by an older version\n")
    with _lock(lock_path), lock_path.open("a") as rival:
        with pytest.raises(BlockingIOError):
            file_lock.lock_exclusive_nowait(rival)


_HOLD_UNTIL_STDIN_CLOSES = """
import sys
from pathlib import Path
from squadron.core import file_lock
f = Path(sys.argv[1]).open("a")
file_lock.lock_exclusive_nowait(f)
print("held", flush=True)
sys.stdin.read()
"""


def test_a_lock_held_by_another_process_is_refused_and_freed_when_it_exits(
    tmp_path: Path,
) -> None:
    lock_path = tmp_path / "x.flock"
    holder = subprocess.Popen(
        [sys.executable, "-c", _HOLD_UNTIL_STDIN_CLOSES, str(lock_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    assert holder.stdin is not None and holder.stdout is not None
    try:
        assert holder.stdout.readline().strip() == "held"
        with lock_path.open("a") as rival:
            with pytest.raises(BlockingIOError):
                file_lock.lock_exclusive_nowait(rival)
    finally:
        holder.stdin.close()
        holder.wait(timeout=10)

    _lock(lock_path).close()


def test_check_lock_support_raises_import_error_when_the_module_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    file_lock.check_lock_support()

    # None in sys.modules makes any later import of the module raise ImportError.
    monkeypatch.setitem(sys.modules, file_lock.LOCK_MODULE, None)
    with pytest.raises(ImportError):
        file_lock.check_lock_support()


# ---------------------------------------------------------------------------
# Each platform's branch, through a fake module
# ---------------------------------------------------------------------------


def _fake_msvcrt(calls: list[tuple[int, int, int]], error: OSError | None = None) -> SimpleNamespace:
    def locking(fd: int, mode: int, nbytes: int) -> None:
        calls.append((fd, mode, nbytes))
        if error is not None:
            raise error

    return SimpleNamespace(LK_UNLCK=0, LK_NBLCK=2, locking=locking)


def test_windows_locks_and_unlocks_one_byte_from_offset_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[int, int, int]] = []
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setitem(sys.modules, "msvcrt", _fake_msvcrt(calls))
    lock_path = tmp_path / "x.flock"
    lock_path.write_text("not empty\n")

    with lock_path.open("a") as lock_file:
        file_lock.lock_exclusive_nowait(lock_file)
        assert lock_file.tell() == 0
        lock_file.seek(0, 2)
        file_lock.unlock(lock_file)
        assert lock_file.tell() == 0
        fd = lock_file.fileno()

    assert calls == [(fd, 2, 1), (fd, 0, 1)]


def test_windows_reports_a_range_locked_elsewhere_as_blocking_io_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    held = PermissionError(errno.EACCES, "Permission denied")
    monkeypatch.setitem(sys.modules, "msvcrt", _fake_msvcrt([], held))

    with (tmp_path / "x.flock").open("a") as lock_file:
        with pytest.raises(BlockingIOError) as excinfo:
            file_lock.lock_exclusive_nowait(lock_file)

    assert excinfo.value.__cause__ is held


def test_windows_passes_other_lock_errors_through(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    bad_fd = OSError(errno.EBADF, "Bad file descriptor")
    monkeypatch.setitem(sys.modules, "msvcrt", _fake_msvcrt([], bad_fd))

    with (tmp_path / "x.flock").open("a") as lock_file:
        with pytest.raises(OSError) as excinfo:
            file_lock.lock_exclusive_nowait(lock_file)

    assert excinfo.value is bad_fd


def test_posix_uses_a_nonblocking_exclusive_flock_and_lock_un(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[object, int]] = []

    def flock(fd: object, operation: int) -> None:
        calls.append((fd, operation))

    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setitem(
        sys.modules, "fcntl", SimpleNamespace(LOCK_EX=2, LOCK_NB=4, LOCK_UN=8, flock=flock)
    )

    with (tmp_path / "x.flock").open("a") as lock_file:
        file_lock.lock_exclusive_nowait(lock_file)
        file_lock.unlock(lock_file)

    assert calls == [(lock_file, 2 | 4), (lock_file, 8)]
