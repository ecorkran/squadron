"""Exclusive, non-blocking lock on an open file, on POSIX and on Windows.

POSIX uses ``fcntl.flock``. Windows has no ``fcntl``, so it uses ``msvcrt.locking`` on
the file's first byte. Windows allows a lock on bytes past the end of the file, so the
file can stay empty. Either way the lock belongs to the open file: it conflicts with any
other open of the same path, in this process or another, and the OS drops it when the
file is closed or its process dies.

The platform module is imported inside each function, never at module level, so this
module imports everywhere and a missing module surfaces only when a lock is taken.
"""

from __future__ import annotations

import errno
import importlib
import sys
from typing import IO

#: The standard-library module that provides file locks on this platform.
LOCK_MODULE = "msvcrt" if sys.platform == "win32" else "fcntl"

# msvcrt locks a byte range; every holder locks this same range, from offset 0.
_LOCKED_BYTES = 1


def check_lock_support() -> None:
    """Raise ``ImportError`` when :data:`LOCK_MODULE` is unavailable."""
    importlib.import_module(LOCK_MODULE)


def lock_exclusive_nowait(lock_file: IO[str]) -> None:
    """Take an exclusive lock on *lock_file*, failing at once if another open file holds it.

    Raises:
        BlockingIOError: another open file holds the lock.
        OSError: locking failed for any other reason.
    """
    if sys.platform == "win32":
        import msvcrt

        lock_file.seek(0)
        try:
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, _LOCKED_BYTES)
        except PermissionError as exc:
            # msvcrt reports a range locked elsewhere as EACCES; flock reports it as
            # EWOULDBLOCK. Callers handle one contention error on every platform.
            raise BlockingIOError(errno.EWOULDBLOCK, exc.strerror) from exc
    else:
        import fcntl

        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)


def unlock(lock_file: IO[str]) -> None:
    """Release a lock taken by :func:`lock_exclusive_nowait`. Raises ``OSError`` on failure."""
    if sys.platform == "win32":
        import msvcrt

        lock_file.seek(0)
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, _LOCKED_BYTES)
    else:
        import fcntl

        fcntl.flock(lock_file, fcntl.LOCK_UN)
