"""Tests for the cross-process git metadata lock (slice 929, design D1/D3/D7)."""

from __future__ import annotations

import errno
import fcntl
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from squadron.codehost import metadata_lock
from squadron.codehost.metadata_lock import MetadataLockError, git_metadata_lock

_LOCK_FILENAME = ".git-metadata.flock"

# Well under the real 60s timeout: an immediate failure lands far below this, a failure
# that wrongly entered the retry loop would not.
_IMMEDIATE_SECONDS = 0.5

_real_flock = fcntl.flock


def _fail_on_unlock(fd: object, operation: int) -> None:
    """Acquire for real; fail the release, as D7's last row describes."""
    if operation == fcntl.LOCK_UN:
        raise OSError(errno.EIO, "simulated unlock failure")
    _real_flock(fd, operation)  # pyright: ignore[reportArgumentType]


# ---------------------------------------------------------------------------
# Acquire/release and timeout (Task C.3a)
# ---------------------------------------------------------------------------


def test_lock_is_acquired_and_released_for_reuse(tmp_path: Path) -> None:
    with git_metadata_lock(tmp_path):
        pass
    with git_metadata_lock(tmp_path):
        pass

    assert (tmp_path / _LOCK_FILENAME).exists()


def test_lock_blocks_a_second_acquirer_until_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patched_timeout = 0.2
    monkeypatch.setattr(metadata_lock, "METADATA_LOCK_TIMEOUT_SECONDS", patched_timeout)

    with (tmp_path / _LOCK_FILENAME).open("a") as holder:
        fcntl.flock(holder, fcntl.LOCK_EX)
        started = time.monotonic()
        with pytest.raises(MetadataLockError, match="timed out"):
            with git_metadata_lock(tmp_path):
                pass
        elapsed = time.monotonic() - started

    assert patched_timeout <= elapsed < patched_timeout + 1.0


# ---------------------------------------------------------------------------
# Immediate-failure mapping (Task C.3b, D7)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    hasattr(os, "getuid") and os.getuid() == 0,
    reason="root bypasses permission checks, so the test would pass for the wrong reason",
)
def test_lock_fails_immediately_on_a_read_only_root(tmp_path: Path) -> None:
    read_only = tmp_path / "read-only"
    read_only.mkdir()
    read_only.chmod(0o500)
    try:
        started = time.monotonic()
        with pytest.raises(MetadataLockError, match="cannot open"):
            with git_metadata_lock(read_only):
                pass
        elapsed = time.monotonic() - started
    finally:
        read_only.chmod(0o700)  # let tmp_path cleanup remove it

    assert elapsed < _IMMEDIATE_SECONDS


def test_lock_fails_immediately_on_non_blocking_io_flock_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[int] = []

    def _no_locks(fd: object, operation: int) -> None:
        calls.append(operation)
        raise OSError(errno.ENOLCK, "no locks available")

    monkeypatch.setattr(fcntl, "flock", _no_locks)

    started = time.monotonic()
    with pytest.raises(MetadataLockError, match="flock failed"):
        with git_metadata_lock(tmp_path):
            pass

    assert time.monotonic() - started < _IMMEDIATE_SECONDS
    assert calls == [fcntl.LOCK_EX | fcntl.LOCK_NB]  # one attempt, no retry loop


def test_lock_fails_with_detail_when_fcntl_is_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # None in sys.modules makes any later 'import fcntl' raise ImportError.
    monkeypatch.setitem(sys.modules, "fcntl", None)

    with pytest.raises(MetadataLockError) as excinfo:
        with git_metadata_lock(tmp_path):
            pass

    assert "fcntl is unavailable" in excinfo.value.detail
    assert sys.platform in excinfo.value.detail


# ---------------------------------------------------------------------------
# Release failure (Task C.3c, D7 last row)
# ---------------------------------------------------------------------------


def test_lock_release_failure_logs_warning_and_does_not_raise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(fcntl, "flock", _fail_on_unlock)

    with caplog.at_level("WARNING"):
        with git_metadata_lock(tmp_path):
            pass

    assert any("Failed to unlock" in r.message for r in caplog.records)


def test_lock_release_failure_does_not_mask_a_body_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(fcntl, "flock", _fail_on_unlock)

    class _BodyError(Exception):
        pass

    with pytest.raises(_BodyError):
        with git_metadata_lock(tmp_path):
            raise _BodyError("the with body failed")


# ---------------------------------------------------------------------------
# Holder death (Task C.4)
# ---------------------------------------------------------------------------

_HOLD_FOREVER = """
import fcntl, sys, time
f = open(sys.argv[1], "a")
fcntl.flock(f, fcntl.LOCK_EX)
time.sleep(60)
"""


def _held_elsewhere(lock_path: Path) -> bool:
    with lock_path.open("a") as probe:
        try:
            fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(probe, fcntl.LOCK_UN)
        return False


def test_a_killed_holder_does_not_block_a_later_acquirer(tmp_path: Path) -> None:
    lock_path = tmp_path / _LOCK_FILENAME
    holder = subprocess.Popen([sys.executable, "-c", _HOLD_FOREVER, str(lock_path)])
    try:
        deadline = time.monotonic() + 10.0
        while not (lock_path.exists() and _held_elsewhere(lock_path)):
            assert time.monotonic() < deadline, "holder subprocess never took the lock"
            time.sleep(0.02)
    finally:
        holder.kill()
        holder.wait()

    started = time.monotonic()
    with git_metadata_lock(tmp_path):
        pass

    assert time.monotonic() - started < 1.0
