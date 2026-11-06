"""A one-commit, history-free repository checkout (slice 177 D3, extracted by slice 421 D4).

A git worktree shares the repository's refs, so a tool-using producer could read later
history (``git show main:…``, ``git log --all``). This sandbox is a fresh repository holding
exactly one commit, the start point, and no ref to later history. It creates no branch and
touches no cf; ``ReplaySandbox`` and the benchmark sandbox compose it.

The ``<dir>.lock`` file (pid + process start time, shared with the PR-review scratch
worktree via ``core.process_lock``) is written before the directory exists, so a
concurrent sweep never reads a half-built sandbox as an orphan.
"""

from __future__ import annotations

import logging
import shutil
from collections.abc import Sequence
from pathlib import Path
from types import TracebackType
from typing import Self

from squadron.core.process_lock import ProcessIdentityUnresolvable, current_process_lock
from squadron.core.process_runner import (
    ProcessCwdNotFoundError,
    ProcessNotFoundError,
    ProcessResult,
    ProcessRunner,
    ProcessTimedOutError,
)

_logger = logging.getLogger(__name__)

#: Wall-clock bound on each git or cf command the sandbox runs.
SANDBOX_COMMAND_TIMEOUT_SECONDS = 120
LOCK_SUFFIX = ".lock"
GITMODULES = ".gitmodules"
_SUBMODULE_SECTION = "[submodule"
PROCESS_FAILURES = (ProcessNotFoundError, ProcessCwdNotFoundError, ProcessTimedOutError)


class SandboxError(Exception):
    """The sandbox could not be built; carries the failing command's stderr when it has one."""


def lock_path(root: Path, name: str) -> Path:
    return root / f"{name}{LOCK_SUFFIX}"


def run_command(runner: ProcessRunner, argv: Sequence[str], cwd: Path | None) -> ProcessResult:
    return runner.run(
        argv, cwd=None if cwd is None else str(cwd), timeout=SANDBOX_COMMAND_TIMEOUT_SECONDS
    )


def remove_tree(path: Path) -> None:
    try:
        shutil.rmtree(path)
    except FileNotFoundError:
        pass  # never created, or already swept: nothing to remove
    except OSError as exc:
        _logger.warning("could not remove replay sandbox %s: %s", path, exc)


def unlink_quietly(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        _logger.warning("could not remove replay lock %s: %s", path, exc)


class HistoryFreeSandbox:
    """Context manager: build the checkout on enter, remove it on every exit path."""

    def __init__(
        self,
        *,
        start_sha: str,
        sandbox_id: str,
        repo_root: Path,
        runner: ProcessRunner,
        root: Path,
    ) -> None:
        self._start_sha = start_sha
        self._sandbox_id = sandbox_id
        # Absolute: the fetch runs under `git -C <sandbox>`, where a relative path would
        # name the sandbox itself.
        self._repo_root = repo_root.resolve()
        self._runner = runner
        self._root = root
        self._kept = False

    @property
    def path(self) -> Path:
        return self._root / self._sandbox_id

    @property
    def start_sha(self) -> str:
        return self._start_sha

    def keep(self) -> None:
        """Leave the sandbox in place on exit (the runner keeps it when a store write fails)."""
        self._kept = True

    def __enter__(self) -> Self:
        self._root.mkdir(parents=True, exist_ok=True)
        built = False
        try:
            self._write_lock()
            self._build_repository()
            built = True
        finally:
            if not built:
                self.cleanup()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if not self._kept:
            self.cleanup()

    def checked(self, *argv: str, cwd: Path | None = None) -> None:
        """Run a command; a failure raises ``SandboxError`` carrying its stderr."""
        command = " ".join(argv)
        try:
            result = run_command(self._runner, argv, cwd)
        except PROCESS_FAILURES as exc:
            raise SandboxError(f"{command}: {exc}") from exc
        if result.returncode != 0:
            raise SandboxError(f"{command} failed: {result.stderr.strip()}")

    def cleanup(self) -> None:
        """Remove the directory, then the lock. Never raises."""
        remove_tree(self.path)
        unlink_quietly(lock_path(self._root, self._sandbox_id))

    def _write_lock(self) -> None:
        try:
            lock = current_process_lock(self._runner)
        except ProcessIdentityUnresolvable as exc:
            raise SandboxError(str(exc)) from exc
        path = lock_path(self._root, self._sandbox_id)
        try:
            path.write_text(lock.to_json())
        except OSError as exc:
            raise SandboxError(f"cannot write sandbox lock {path}: {exc}") from exc

    def _build_repository(self) -> None:
        sandbox = str(self.path)
        self.checked("git", "init", "-q", sandbox)
        self.checked(
            "git", "-C", sandbox, "fetch", "-q", "--depth", "1", str(self._repo_root), self._start_sha
        )
        self.checked("git", "-C", sandbox, "checkout", "-q", "--detach", "FETCH_HEAD")
        if self._declares_submodules():
            raise SandboxError(
                f"start commit {self._start_sha} declares submodules in {GITMODULES}; "
                "submodule replay is not supported"
            )

    def _declares_submodules(self) -> bool:
        """Whether ``.gitmodules`` has a submodule entry; squadron tracks an empty one."""
        path = self.path / GITMODULES
        if not path.is_file():
            return False
        try:
            return _SUBMODULE_SECTION in path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise SandboxError(f"cannot read {GITMODULES} at {self._start_sha}: {exc}") from exc
