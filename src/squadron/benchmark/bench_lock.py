"""The benchmark process lock (slice 424 D4, State Management).

``<benchmark root>/<benchmark_id>.lock``, the same pid + process-start-time lock 177's
sandboxes use. A second live invocation of one benchmark refuses; a lock whose owner is gone
(or that cannot be read) is taken over, never an error.
"""

from __future__ import annotations

import logging
import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from squadron.benchmark.bench_plan import BenchmarkRefusal
from squadron.core.process_lock import (
    ProcessLock,
    current_process_lock,
    is_orphan,
    read_lock,
)
from squadron.core.process_runner import ProcessRunner
from squadron.replay.history_free_sandbox import unlink_quietly

LOCK_SUFFIX = ".lock"
GUARD_SUFFIX = ".guard"
_logger = logging.getLogger(__name__)


def _guard_path(lock_path: Path) -> Path:
    return lock_path.with_name(f"{lock_path.name}{GUARD_SUFFIX}")


@contextmanager
def _acquisition_guard(lock_path: Path) -> Iterator[None]:
    """Serialize the take-or-take-over step of one benchmark's lock across processes.

    Without it two processes can both judge a stale lock dead, one links its own lock and
    the other then deletes that fresh lock and links a second: both hold it. The guard is an
    ``flock`` on a sibling file, held only for the short read, delete and link; closing the
    file drops it. POSIX only, like the project run lock.
    """
    try:
        import fcntl
    except ImportError as exc:
        raise BenchmarkRefusal("benchmark locks need POSIX file locking (fcntl)") from exc
    with _guard_path(lock_path).open("a") as guard:
        fcntl.flock(guard, fcntl.LOCK_EX)
        yield


class BenchmarkLock:
    """Held from a successful ``acquire`` until ``release``; also a context manager."""

    def __init__(self, path: Path, owner: ProcessLock) -> None:
        self._path = path
        self.owner = owner

    @classmethod
    def acquire(cls, root: Path, benchmark_id: str, runner: ProcessRunner) -> BenchmarkLock:
        """Take the lock, taking over a dead owner's; refuse while a live process holds it."""
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"{benchmark_id}{LOCK_SUFFIX}"
        owner = current_process_lock(runner)
        # The owner is written to a private file first and linked into place, so the lock
        # never exists half-written: another process reading it mid-create would see an
        # unreadable lock, call its owner dead and take it over.
        staged = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
        staged.write_text(owner.to_json())
        try:
            with _acquisition_guard(path):
                return cls._link_into_place(path, staged, owner, benchmark_id, runner)
        finally:
            unlink_quietly(staged)

    @classmethod
    def _link_into_place(
        cls,
        path: Path,
        staged: Path,
        owner: ProcessLock,
        benchmark_id: str,
        runner: ProcessRunner,
    ) -> BenchmarkLock:
        for _attempt in range(2):
            try:
                os.link(staged, path)  # atomic, and fails if the lock exists
            except FileExistsError:
                holder = read_lock(path)
                if not is_orphan(runner, holder):
                    pid = "unknown" if holder is None else holder.pid
                    raise BenchmarkRefusal(
                        f"benchmark {benchmark_id} is already running (pid {pid}); "
                        f"wait for it or stop it first"
                    ) from None
                _logger.warning(
                    "taking over the lock of a benchmark that is no longer running: %s", path
                )
                unlink_quietly(path)
                continue
            return cls(path, owner)
        raise BenchmarkRefusal(
            f"benchmark {benchmark_id}: could not take {path}; another process won it"
        )

    def release(self) -> None:
        """Remove the lock file and its guard. Never raises.

        Removing the guard is safe: it only matters while a stale lock is being taken over,
        and a released lock is not stale. A crash leaves it behind, and the next acquirer
        reuses it.
        """
        unlink_quietly(self._path)
        unlink_quietly(_guard_path(self._path))

    def __enter__(self) -> BenchmarkLock:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.release()
