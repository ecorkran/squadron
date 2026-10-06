"""One mutating run per checkout (slice 197 D11).

Batches and item resumes check out branches and move cf's slice. Two of them in one
checkout would interleave, and race on ``report.json``. ``project_run_lock`` takes an
exclusive, non-blocking ``flock`` on ``{git dir}/squadron-run.flock``. The git dir is
per worktree, so separate registered worktrees still run in parallel.

It never waits: a held lock fails at once, so the caller decides when to retry. A
killed holder releases the lock when the OS closes its file, so nothing goes stale.

POSIX only, as ``codehost/metadata_lock.py``: ``fcntl`` is imported inside the
function, so this module imports on Windows, and taking the lock there raises.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TextIO, cast

from squadron.pipeline.git_ops import GitEnvironmentError
from squadron.pipeline.models import PipelineDefinition, StepConfig
from squadron.pipeline.steps import StepTypeName
from squadron.pipeline.steps.utils import unpack_inner_steps
from squadron.review.git_utils import run_git

_logger = logging.getLogger(__name__)

_LOCK_FILENAME = "squadron-run.flock"


# Steps that commit or move cf's arch, slice or phase. A loop mutates when it commits
# each round; every other step mutates only through what it nests.
_MUTATING_STEP_TYPES = frozenset(
    {
        StepTypeName.DESIGN,
        StepTypeName.TASKS,
        StepTypeName.IMPLEMENT,
        StepTypeName.DEVLOG,
        StepTypeName.BRANCH,
    }
)
_COMMIT_EACH_ITERATION = "commit_each_iteration"


def pipeline_mutates(definition: PipelineDefinition) -> bool:
    """Whether any step, nested steps included, commits or moves cf state (D11)."""
    return any(_step_mutates(s) for s in definition.steps)


def _step_mutates(step: StepConfig) -> bool:
    if step.step_type in _MUTATING_STEP_TYPES:
        return True
    if step.step_type == StepTypeName.LOOP and step.config.get(_COMMIT_EACH_ITERATION) is True:
        return True
    nested = step.config.get("steps")
    if not isinstance(nested, list):
        return False
    raw_steps = [cast(dict[str, object], s) for s in cast(list[object], nested) if isinstance(s, dict)]
    return any(_step_mutates(inner) for inner in unpack_inner_steps(raw_steps))


class RunLockError(Exception):
    """The project run lock could not be taken; nothing ran."""


class RunLockHeldError(RunLockError):
    """Another squadron run in this checkout holds the lock."""


@contextmanager
def project_run_lock(cwd: str) -> Iterator[Path]:
    """Hold the checkout's run lock for the ``with`` body; yields the lock path.

    Raises:
        GitEnvironmentError: ``git rev-parse --git-dir`` failed or timed out.
        RunLockHeldError: another run holds the lock.
        RunLockError: no ``fcntl``, or the lock file could not be opened or locked.
    """
    lock_path = _git_dir(cwd) / _LOCK_FILENAME
    lock_file = _open(lock_path)
    try:
        _acquire(lock_file, lock_path)
    except BaseException:
        lock_file.close()
        raise
    try:
        yield lock_path
    finally:
        # Closing the descriptor drops the flock.
        lock_file.close()


def _git_dir(cwd: str) -> Path:
    result = run_git(["rev-parse", "--path-format=absolute", "--git-dir"], cwd=cwd)
    if result is None or result.returncode != 0:
        detail = result.stderr.strip() if result is not None else "git timed out or could not run"
        message = f"cannot find the git dir for the project run lock: {detail}"
        _logger.error(message)
        raise GitEnvironmentError(message)
    return Path(result.stdout.strip())


def _open(lock_path: Path) -> TextIO:
    try:
        import fcntl  # noqa: F401  # pyright: ignore[reportUnusedImport]
    except ImportError as exc:
        message = f"project run lock {lock_path}: fcntl is unavailable on {sys.platform!r}"
        _logger.error(message)
        raise RunLockError(message) from exc
    try:
        return lock_path.open("a")
    except OSError as exc:
        message = f"project run lock {lock_path}: cannot open: {exc.strerror}"
        _logger.error(message)
        raise RunLockError(message) from exc


def _acquire(lock_file: TextIO, lock_path: Path) -> None:
    import fcntl

    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        message = (
            f"another squadron run holds the project lock ({lock_path}); "
            "one mutating run per project at a time"
        )
        _logger.error(message)
        raise RunLockHeldError(message) from None
    except OSError as exc:
        message = f"project run lock {lock_path}: flock failed: {exc.strerror}"
        _logger.error(message)
        raise RunLockError(message) from exc
