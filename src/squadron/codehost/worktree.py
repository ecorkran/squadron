"""Scratch-worktree lifecycle for reviewing a pull request's code (slice 382, design D3).

A PR review's tool jail is a git worktree checked out from a fetched, namespaced ref —
never the caller's own working tree, so a review of someone else's branch cannot touch
the operator's uncommitted work. This module owns that worktree's full lifecycle: create,
lock (so a concurrent orphan sweep does not remove a worktree still in use), sweep orphans
left behind by a crashed or killed prior run, and remove unconditionally on every exit path.

A malformed lock is treated as an orphan, never as an exception — a parse error here must
not fail every subsequent ``sq review pr`` (see ``sweep_orphans``).
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import cast

from squadron.codehost.errors import CodeHostError
from squadron.codehost.models import PullRequestRecord
from squadron.codehost.refs import GIT_FETCH_TIMEOUT_SECONDS, GIT_QUERY_TIMEOUT_SECONDS
from squadron.core.process_runner import ProcessRunner, ProcessTimedOutError

_logger = logging.getLogger(__name__)

_LOCK_FILENAME = "lock.json"
_CLAIM_SUFFIX = ".claim"


class WorktreeError(CodeHostError):
    """Base for every scratch-worktree failure."""


class WorktreeCreationError(WorktreeError):
    """``git worktree add`` failed."""

    def __init__(self, path: Path, detail: str, *, fix_hint: str | None = None) -> None:
        super().__init__(f"failed to create worktree at {path}: {detail}", fix_hint=fix_hint)
        self.path = path
        self.detail = detail


class SubmoduleUnfetchableError(WorktreeError):
    """A submodule could not be initialized (auth failure, gone, unreachable)."""

    def __init__(self, submodule_path: str, detail: str, *, fix_hint: str | None = None) -> None:
        super().__init__(f"submodule unfetchable: {submodule_path}: {detail}", fix_hint=fix_hint)
        self.submodule_path = submodule_path
        self.detail = detail


class SubmoduleTimeoutError(WorktreeError):
    """A submodule init exceeded its bound."""

    def __init__(self, submodule_path: str, seconds: float, *, fix_hint: str | None = None) -> None:
        super().__init__(f"submodule init exceeded {seconds}s: {submodule_path}", fix_hint=fix_hint)
        self.submodule_path = submodule_path
        self.seconds = seconds


class ProcessIdentityUnresolvableError(WorktreeError):
    """This process's own start time could not be determined via ``ps``.

    Raised before any worktree exists — a lock written without a resolvable start time
    could never be matched on readback, silently defeating the orphan sweep.
    """

    def __init__(self, pid: int, *, fix_hint: str | None = None) -> None:
        super().__init__(
            f"could not determine this process's own start time via 'ps' (pid {pid})",
            fix_hint=fix_hint,
        )
        self.pid = pid


@dataclass(frozen=True)
class WorktreeLock:
    """The lock a live ``ScratchWorktree`` writes to its directory.

    ``started_at`` is the *process's* start time, not the moment the lock was written — a
    pid the OS has since recycled for an unrelated process must not read as still owning
    this worktree.
    """

    pid: int
    started_at: float


def _worktree_root() -> Path:
    """``~/.config/squadron/worktrees/`` — reuses the config-dir migration pattern.

    Not a second hardcoded ``~/.config/squadron``: this mirrors
    ``squadron.config.manager._config_dir`` exactly (same base), because that function is
    private to its own module and this is a sibling concern (scratch state, not config).
    """
    return Path.home() / ".config" / "squadron" / "worktrees"


def _current_process_start_time(runner: ProcessRunner) -> float:
    """The current process's start time, as epoch seconds.

    No stdlib call returns this portably (Linux has ``/proc``, macOS does not), so this
    shells out to ``ps -o lstart=``, whose output ``lstart`` format both BSD (macOS) and
    GNU (Linux) ``ps`` accept. Parsed as local time, matching the host clock the same
    ``ps`` invocation reads — always same-host, since a lock is only ever read back by a
    process on the machine that wrote it.

    Unlike ``_process_start_time`` (used for other processes, where "gone" is an expected,
    handled outcome), the *current* process is always running — a failure to resolve its
    own start time means ``ps`` itself is broken or missing, which is an environment fault
    this must surface loudly rather than write a lock that can never match on readback.
    """
    pid = os.getpid()
    start_time = _process_start_time(runner, pid)
    if start_time is None:
        raise ProcessIdentityUnresolvableError(pid)
    return start_time


def _process_start_time(runner: ProcessRunner, pid: int) -> float | None:
    """The start time of *pid*, as epoch seconds, or ``None`` if it is not running."""
    result = runner.run(
        ["ps", "-o", "lstart=", "-p", str(pid)],
        cwd=None,
        timeout=GIT_QUERY_TIMEOUT_SECONDS,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        return datetime.strptime(result.stdout.strip(), "%a %b %d %H:%M:%S %Y").timestamp()
    except ValueError:
        # A ps output format this parser does not recognize is not evidence the process
        # is dead — treat as "cannot determine", the same as a missing pid, so a live
        # owner is never mistaken for an orphan due to a parsing gap.
        _logger.warning("Could not parse 'ps' start-time output for pid %d: %r", pid, result.stdout)
        return None


def _read_lock(lock_path: Path) -> WorktreeLock | None:
    """Parse *lock_path*, or ``None`` for any of: missing, unreadable, malformed, incomplete.

    Every one of these reasons is a single treat-as-orphan path (see ``sweep_orphans``) —
    this function never raises.
    """
    try:
        raw = lock_path.read_text()
    except OSError:
        return None
    try:
        parsed: object = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    data = cast(dict[str, object], parsed)
    if "pid" not in data or "started_at" not in data:
        return None
    raw_pid = data["pid"]
    raw_started_at = data["started_at"]
    if not isinstance(raw_pid, int) or not isinstance(raw_started_at, (int, float)):
        return None
    return WorktreeLock(pid=raw_pid, started_at=float(raw_started_at))


def _claim_path(worktree_path: Path) -> Path:
    """The claim file for *worktree_path*, as a sibling rather than a child.

    ``git worktree add`` refuses a target directory that already exists, so the claim
    cannot be written inside the worktree it claims. It sits beside it instead, and
    ``sweep_orphans`` skips it for free: that loop already ignores non-directories.
    """
    return worktree_path.parent / f"{worktree_path.name}{_CLAIM_SUFFIX}"


def _write_claim(path: Path, lock: WorktreeLock) -> None:
    """Record *lock*'s owner as the creator of *path*, before the worktree exists.

    Same payload as the lock, so ``_read_lock``/``_is_orphan`` interpret both with one
    set of rules: a claim whose writer died is swept exactly like a dead lock.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"pid": lock.pid, "started_at": lock.started_at}))


def _unlink_claim(path: Path) -> None:
    """Drop a claim file. Never raises — a stray claim is swept, not fatal."""
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        _logger.warning("Failed to remove worktree claim %s: %s", path, exc)


def _is_orphan(runner: ProcessRunner, lock: WorktreeLock | None) -> bool:
    """Whether the owner recorded by *lock* is gone, or a different process entirely."""
    if lock is None:
        return True
    live_start = _process_start_time(runner, lock.pid)
    if live_start is None:
        return True
    # A tight tolerance, not exact equality: `ps` truncates to whole seconds, so a lock
    # written and re-read within the same second is byte-identical, but any real
    # cross-process comparison stays well outside a 2-second window unless the pid was
    # actually recycled.
    return abs(live_start - lock.started_at) > 2.0


def sweep_orphans(runner: ProcessRunner, checkout_cwd: str, root: Path | None = None) -> None:
    """Remove worktrees whose owning process is gone. Never raises.

    ``checkout_cwd`` is the trusted checkout the scratch worktrees were added from — ``git
    worktree remove``/``prune`` are subcommands of that repository, distinct from ``root``
    (where the scratch directories themselves live on disk).

    A crashed or killed ``sq review pr`` leaves its worktree and lock behind; this is the
    only cleanup path for that case; run at the start of every new
    :class:`ScratchWorktree` creation. A malformed or unreadable lock is swept the same as
    a confirmed-dead owner — the alternative, raising out of a parse error, would fail
    every subsequent ``sq review pr`` over one corrupted file (design D3).
    """
    worktree_root = root if root is not None else _worktree_root()
    if not worktree_root.is_dir():
        return

    for entry in sorted(worktree_root.iterdir()):
        if not entry.is_dir():
            continue  # also skips the sibling .claim files (see _claim_path)
        lock_path = entry / _LOCK_FILENAME
        lock = _read_lock(lock_path)
        if lock is not None and not _is_orphan(runner, lock):
            continue  # live owner, matching pid and start time — leave it alone

        if lock is None:
            # No lock yet does not mean abandoned: `git worktree add` refuses a
            # pre-existing target directory, so the claim cannot live inside the
            # worktree and a live creator is briefly indistinguishable from a crashed
            # one. The sibling claim closes that window — a live claimant is still
            # setting up, and sweeping it would delete a worktree out from under a
            # concurrent run.
            claim = _read_lock(_claim_path(entry))
            if claim is not None and not _is_orphan(runner, claim):
                continue

        reason = "no readable/parseable lock" if lock is None else "owner process is gone"
        _logger.warning("Sweeping orphaned worktree %s (%s)", entry, reason)
        try:
            runner.run(
                ["git", "worktree", "remove", "--force", str(entry)],
                cwd=checkout_cwd,
                timeout=GIT_QUERY_TIMEOUT_SECONDS,
            )
        except ProcessTimedOutError:
            _logger.warning(
                "Timed out removing orphaned worktree %s via git; will unlink directly", entry
            )
        if entry.exists():
            _rmtree(entry)

    try:
        runner.run(["git", "worktree", "prune"], cwd=checkout_cwd, timeout=GIT_QUERY_TIMEOUT_SECONDS)
    except ProcessTimedOutError:
        _logger.warning("'git worktree prune' timed out after sweeping orphans")


def _rmtree(path: Path) -> None:
    """Remove *path* recursively. Never raises — a leftover directory is logged, not fatal."""
    try:
        shutil.rmtree(path)
    except OSError as exc:
        _logger.warning("Failed to remove leftover worktree directory %s: %s", path, exc)


class ScratchWorktree:
    """A scratch git worktree checked out from a pull request's fetched head, for one run.

    Use as a context manager. ``__enter__`` sweeps orphans, creates the worktree, writes
    the lock, and initializes submodules; ``__exit__`` removes the worktree unconditionally
    — success, exception, or (via the caller's own timeout handling) a review that ran past
    a bound.

    ``head_ref`` is the *local, namespaced* ref 381 already fetched
    (``FetchedRange.head_ref``, e.g. ``refs/squadron/pr/<remote>/<number>/head``) — not
    ``PullRequestRecord.head_ref``, which names the PR's ref on its remote and was never
    fetched into this checkout.
    """

    def __init__(
        self,
        runner: ProcessRunner,
        record: PullRequestRecord,
        head_ref: str,
        run_id: str,
        checkout_cwd: str,
        root: Path | None = None,
    ) -> None:
        self._runner = runner
        self._record = record
        self._head_ref = head_ref
        self._run_id = run_id
        self._checkout_cwd = checkout_cwd
        self._root = root if root is not None else _worktree_root()
        self._path: Path | None = None

    @property
    def path(self) -> Path:
        """The worktree's filesystem path. Only valid inside the ``with`` block."""
        if self._path is None:
            raise RuntimeError("ScratchWorktree.path accessed outside its 'with' block")
        return self._path

    def __enter__(self) -> ScratchWorktree:
        sweep_orphans(self._runner, self._checkout_cwd, self._root)

        self._root.mkdir(parents=True, exist_ok=True)
        path = self._root / f"{self._record.path_key}-{self._run_id}"
        self._path = path

        # Claim the path *before* it exists on disk. Between `git worktree add` and the
        # lock write, the directory is real but unlocked, and a concurrent run's sweep
        # would read it as an unclaimed orphan and remove it mid-setup. The claim closes
        # that window from the outside, since `add` will not accept an existing directory.
        lock = WorktreeLock(pid=os.getpid(), started_at=_current_process_start_time(self._runner))
        claim_path = _claim_path(path)
        _write_claim(claim_path, lock)

        try:
            result = self._runner.run(
                ["git", "worktree", "add", "--detach", str(path), self._head_ref],
                cwd=self._checkout_cwd,
                timeout=GIT_QUERY_TIMEOUT_SECONDS,
            )
            if result.returncode != 0:
                _logger.error("git worktree add failed for %s: %s", path, result.stderr)
                raise WorktreeCreationError(path, result.stderr)

            # The lock must exist before any submodule work — it is what the sweep uses to
            # tell "worktree exists, still being set up" from "worktree exists, abandoned."
            (path / _LOCK_FILENAME).write_text(
                json.dumps({"pid": lock.pid, "started_at": lock.started_at})
            )
        except BaseException:
            # The claim outlives this process only as sweepable litter; drop it eagerly so
            # a failed creation leaves nothing behind. Re-raised immediately.
            _unlink_claim(claim_path)
            raise

        # Handed off: the real lock now speaks for this worktree.
        _unlink_claim(claim_path)

        try:
            self._init_submodules(path)
        except WorktreeError:
            self._remove(path)
            raise

        return self

    def _init_submodules(self, path: Path) -> None:
        try:
            result = self._runner.run(
                ["git", "submodule", "update", "--init", "--recursive"],
                cwd=str(path),
                timeout=GIT_FETCH_TIMEOUT_SECONDS,
            )
        except ProcessTimedOutError as exc:
            submodule_path = _submodule_path_from_output(exc.argv, "") or "(unknown submodule)"
            _logger.error(
                "Submodule init exceeded %ss for %s: %s",
                GIT_FETCH_TIMEOUT_SECONDS,
                path,
                submodule_path,
            )
            raise SubmoduleTimeoutError(submodule_path, GIT_FETCH_TIMEOUT_SECONDS) from exc

        if result.returncode != 0:
            submodule_path = (
                _submodule_path_from_output(result.argv, result.stderr) or "(unknown submodule)"
            )
            _logger.error("Submodule unfetchable in %s: %s: %s", path, submodule_path, result.stderr)
            raise SubmoduleUnfetchableError(submodule_path, result.stderr)

    def __exit__(self, *exc_info: object) -> None:
        if self._path is not None:
            self._remove(self._path)

    def _remove(self, path: Path) -> None:
        # Documented exception to "every try/except re-raises": __exit__ must not mask the
        # original exception (if any) that is already propagating, and per design D3 the
        # review's own result stands regardless of whether cleanup succeeds. A leftover
        # directory is an operational nuisance, not a correctness failure — so every branch
        # below logs at WARNING and falls through to a direct filesystem removal attempt
        # rather than raising.
        try:
            result = self._runner.run(
                ["git", "worktree", "remove", "--force", str(path)],
                cwd=self._checkout_cwd,
                timeout=GIT_QUERY_TIMEOUT_SECONDS,
            )
        except ProcessTimedOutError:
            _logger.warning("Timed out removing worktree %s; may require manual cleanup", path)
        else:
            if result.returncode != 0:
                _logger.warning("Failed to remove worktree %s: %s", path, result.stderr)
        if path.exists():
            _rmtree(path)


def _submodule_path_from_output(argv: Sequence[str], stderr: str) -> str | None:
    """Best-effort extraction of the failing submodule's path from git's own output.

    ``git submodule update`` reports the path in its stderr (e.g. ``Failed to clone
    'vendor/lib'``); falls back to ``None`` (caller substitutes a placeholder) rather than
    reporting the whole command failed generically.
    """
    for line in stderr.splitlines():
        if "'" in line:
            parts = line.split("'")
            if len(parts) >= 2:
                return parts[1]
    return None
