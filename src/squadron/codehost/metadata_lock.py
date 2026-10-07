"""Cross-process lock around git's worktree-metadata calls (slice 929, issue #133).

Git does not serialize writes to a repository's shared worktree metadata
(``.git/worktrees/<name>/``). Two concurrent ``git worktree add``/``remove``/``prune``
calls against one checkout can read a sibling's admin directory mid-write and fail with
``fatal: failed to read .git/worktrees/<sibling>/commondir``. ``git_metadata_lock``
takes an exclusive ``flock`` around each such call so only one runs at a time.

POSIX only (design D5): ``fcntl`` is imported inside the lock functions, never at module
level, so importing this module (and ``worktree``, which ``review_pr`` imports eagerly)
still works on Windows. Taking the lock there raises ``MetadataLockError``.

One lock file serves every repository: ``.git-metadata.flock`` in the scratch-worktree
root (``~/.config/squadron/worktrees/`` by default), design D2.
"""

from __future__ import annotations

import logging
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TextIO

from squadron.codehost.errors import CodeHostError
from squadron.codehost.git_refs import GIT_QUERY_TIMEOUT_SECONDS

_logger = logging.getLogger(__name__)

# The lock file's name inside the worktree root.
_LOCK_FILENAME = ".git-metadata.flock"

# How often a waiting acquirer retries the non-blocking flock (design D3).
_METADATA_LOCK_POLL_SECONDS = 0.05

# Derived, not chosen independently (D3): every wrapped git call is itself bounded by
# GIT_QUERY_TIMEOUT_SECONDS, so a waiter gets room for one full holder plus margin.
METADATA_LOCK_TIMEOUT_SECONDS = 2 * GIT_QUERY_TIMEOUT_SECONDS


class MetadataLockError(CodeHostError):
    """The git metadata lock could not be taken: timeout, filesystem error, or no ``fcntl``.

    ``timed_out`` separates "held elsewhere, waiting may help" from the failures where
    waiting never helps (missing ``fcntl``, unwritable root, persistent flock error).
    """

    def __init__(self, lock_path: Path, detail: str, *, timed_out: bool = False) -> None:
        super().__init__(f"git metadata lock {lock_path}: {detail}")
        self.lock_path = lock_path
        self.detail = detail
        self.timed_out = timed_out


@contextmanager
def git_metadata_lock(root: Path) -> Iterator[None]:
    """Hold the exclusive git-metadata lock under *root* for the ``with`` body.

    Every failure to acquire raises ``MetadataLockError`` (design D7). A fresh file is
    opened per acquisition and never shared (D1): ``flock`` belongs to the open file
    description, so this serializes threads in one process as well as processes.
    """
    lock_path = root / _LOCK_FILENAME
    try:
        # Availability probe only (D5); the helpers below re-import it for use.
        import fcntl  # noqa: F401  # pyright: ignore[reportUnusedImport]
    except ImportError as exc:
        raise MetadataLockError(
            lock_path, f"fcntl is unavailable on platform {sys.platform!r}: {exc}"
        ) from exc

    try:
        root.mkdir(parents=True, exist_ok=True)
        lock_file = lock_path.open("a")
    except OSError as exc:
        raise MetadataLockError(lock_path, f"cannot open {lock_path}: {exc.strerror}") from exc

    try:
        _acquire(lock_file, lock_path)
    except BaseException:
        _close(lock_file, lock_path)
        raise
    try:
        yield
    finally:
        _release(lock_file, lock_path)


def _acquire(lock_file: TextIO, lock_path: Path) -> None:
    """Poll a non-blocking exclusive flock until held or the deadline passes (D3)."""
    import fcntl

    timeout = METADATA_LOCK_TIMEOUT_SECONDS
    deadline = time.monotonic() + timeout
    while True:
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except BlockingIOError:
            pass  # held elsewhere — the only error that is retried (D7)
        except OSError as exc:
            # ENOLCK, EBADF and the like will not clear by waiting; fail now rather than
            # pass a persistent error off as a timeout (D7).
            raise MetadataLockError(lock_path, f"flock failed: {exc.strerror}") from exc
        if time.monotonic() >= deadline:
            raise MetadataLockError(
                lock_path, f"timed out after {timeout}s waiting for the lock", timed_out=True
            )
        time.sleep(_METADATA_LOCK_POLL_SECONDS)


def _release(lock_file: TextIO, lock_path: Path) -> None:
    """Unlock and close. Never raises (D7): a raise here would mask the body's exception."""
    import fcntl

    try:
        fcntl.flock(lock_file, fcntl.LOCK_UN)
    except OSError as exc:
        # Swallowed on purpose: closing the descriptor below releases the lock anyway.
        _logger.warning("Failed to unlock git metadata lock %s: %s", lock_path, exc)
    _close(lock_file, lock_path)


def _close(lock_file: TextIO, lock_path: Path) -> None:
    """Close the lock file. Never raises — the kernel drops the lock with the descriptor."""
    try:
        lock_file.close()
    except OSError as exc:
        _logger.warning("Failed to close git metadata lock %s: %s", lock_path, exc)
