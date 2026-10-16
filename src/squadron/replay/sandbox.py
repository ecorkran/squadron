"""A history-free sandbox repository for one producer replay (slice 177 D3).

A git worktree shares the repository's refs, so a tool-using producer could read the
original artifact from ``main`` (``git show main:…``, ``git log --all``). The sandbox is a
fresh repository holding exactly one commit, the replay's start point, and no ref to
later history. It is registered with cf as ``replay-<replay_id>`` because cf resolves the
project from the cwd and ``P4``/``P5`` run cf operations, and it is removed on exit.

The ``<dir>.lock`` file (pid + process start time, shared with the PR-review scratch
worktree via ``core.process_lock``) is written before the directory exists, so a
concurrent sweep never reads a half-built sandbox as an orphan.
"""

from __future__ import annotations

import json
import logging
import shutil
from collections.abc import Sequence
from pathlib import Path
from types import TracebackType
from typing import Self, cast

from squadron.core.process_lock import (
    ProcessIdentityUnresolvable,
    current_process_lock,
    is_orphan,
    read_lock,
)
from squadron.core.process_runner import (
    ProcessCwdNotFoundError,
    ProcessNotFoundError,
    ProcessResult,
    ProcessRunner,
    ProcessTimedOutError,
)
from squadron.stats.planning_docs import UnknownSliceError, plan_file_for

_logger = logging.getLogger(__name__)

#: Wall-clock bound on each git or cf command the sandbox runs.
SANDBOX_COMMAND_TIMEOUT_SECONDS = 120
LOCK_SUFFIX = ".lock"
#: A sandbox's cf project is ``CF_PROJECT_PREFIX`` + its replay id.
CF_PROJECT_PREFIX = "replay-"
BRANCH_PREFIX = "replay/"
_GITMODULES = ".gitmodules"
_SUBMODULE_SECTION = "[submodule"
_PROCESS_FAILURES = (ProcessNotFoundError, ProcessCwdNotFoundError, ProcessTimedOutError)


class SandboxError(Exception):
    """The sandbox could not be built; carries the failing command's stderr when it has one."""


def replays_root() -> Path:
    """``~/.config/squadron/replays/`` — sibling of the PR-review ``worktrees`` directory."""
    return Path.home() / ".config" / "squadron" / "replays"


def _lock_path(root: Path, name: str) -> Path:
    return root / f"{name}{LOCK_SUFFIX}"


def _run(runner: ProcessRunner, argv: Sequence[str], cwd: Path | None) -> ProcessResult:
    return runner.run(
        argv, cwd=None if cwd is None else str(cwd), timeout=SANDBOX_COMMAND_TIMEOUT_SECONDS
    )


class ReplaySandbox:
    """Context manager: build the sandbox on enter, remove it on every exit path."""

    def __init__(
        self,
        *,
        start_sha: str,
        replay_id: str,
        repo_root: Path,
        slice_index: int,
        runner: ProcessRunner,
        root: Path | None = None,
    ) -> None:
        self._start_sha = start_sha
        self._replay_id = replay_id
        # Absolute: the fetch runs under `git -C <sandbox>`, where a relative path would
        # name the sandbox itself.
        self._repo_root = repo_root.resolve()
        self._slice_index = slice_index
        self._runner = runner
        self._root = root if root is not None else replays_root()
        self._kept = False
        self._registered = False

    @property
    def path(self) -> Path:
        return self._root / self._replay_id

    @property
    def cf_project(self) -> str:
        return f"{CF_PROJECT_PREFIX}{self._replay_id}"

    @property
    def branch(self) -> str:
        return f"{BRANCH_PREFIX}{self._replay_id}"

    def keep(self) -> None:
        """Leave the sandbox in place on exit (the runner keeps it when a store write fails)."""
        self._kept = True

    def __enter__(self) -> Self:
        self._root.mkdir(parents=True, exist_ok=True)
        built = False
        try:
            self._write_lock()
            self._build_repository()
            self._register_with_cf()
            built = True
        finally:
            if not built:
                self._cleanup()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if not self._kept:
            self._cleanup()

    def _write_lock(self) -> None:
        try:
            lock = current_process_lock(self._runner)
        except ProcessIdentityUnresolvable as exc:
            raise SandboxError(str(exc)) from exc
        _lock_path(self._root, self._replay_id).write_text(lock.to_json())

    def _build_repository(self) -> None:
        sandbox = str(self.path)
        self._checked("git", "init", "-q", sandbox)
        self._checked(
            "git", "-C", sandbox, "fetch", "-q", "--depth", "1", str(self._repo_root), self._start_sha
        )
        self._checked("git", "-C", sandbox, "checkout", "-q", "--detach", "FETCH_HEAD")
        self._checked("git", "-C", sandbox, "switch", "-q", "-c", self.branch)
        if self._declares_submodules():
            raise SandboxError(
                f"start commit {self._start_sha} declares submodules in {_GITMODULES}; "
                "submodule replay is not supported"
            )

    def _declares_submodules(self) -> bool:
        """Whether ``.gitmodules`` has a submodule entry; squadron tracks an empty one."""
        path = self.path / _GITMODULES
        return path.is_file() and _SUBMODULE_SECTION in path.read_text(encoding="utf-8")

    def _register_with_cf(self) -> None:
        """Register the sandbox as a cf project and point cf at the slice's initiative.

        The branch guard compares the checkout to ``git.integration_branch``, so the sandbox
        branch is set as its integration branch; and a fresh cf project has no slice plan, so
        ``cf set arch`` names the initiative whose plan lists the slice (Task 1 spike).
        """
        initiative = self._initiative()
        self._checked("cf", "init", "--lite", "--no-ide", "--name", self.cf_project, cwd=self.path)
        self._registered = True
        self._checked("cf", "config", "set", "git.integration_branch", self.branch, cwd=self.path)
        self._checked("cf", "set", "arch", initiative, cwd=self.path)

    def _initiative(self) -> str:
        """The initiative index of the slice plan listing the slice, at the start point."""
        try:
            plan = plan_file_for(self._slice_index, self.path)
        except UnknownSliceError as exc:
            raise SandboxError(
                f"slice {self._slice_index} is in no slice plan at start commit {self._start_sha}"
            ) from exc
        return plan.name.split("-", 1)[0]

    def _checked(self, *argv: str, cwd: Path | None = None) -> None:
        """Run a command; a failure raises ``SandboxError`` carrying its stderr."""
        command = " ".join(argv)
        try:
            result = _run(self._runner, argv, cwd)
        except _PROCESS_FAILURES as exc:
            raise SandboxError(f"{command}: {exc}") from exc
        if result.returncode != 0:
            raise SandboxError(f"{command} failed: {result.stderr.strip()}")

    def _cleanup(self) -> None:
        """Remove the cf project, the directory, then the lock. Never raises."""
        if self._registered:
            _remove_cf_project(self._runner, self.cf_project)
        _remove_tree(self.path)
        _unlink(_lock_path(self._root, self._replay_id))


def _remove_cf_project(runner: ProcessRunner, name: str) -> None:
    try:
        result = _run(runner, ["cf", "project", "rm", name, "--yes"], None)
    except _PROCESS_FAILURES as exc:
        _logger.warning("could not remove cf project %s: %s", name, exc)
        return
    if result.returncode != 0:
        _logger.warning("could not remove cf project %s: %s", name, result.stderr.strip())


def _remove_tree(path: Path) -> None:
    try:
        shutil.rmtree(path)
    except FileNotFoundError:
        pass  # never created, or already swept: nothing to remove
    except OSError as exc:
        _logger.warning("could not remove replay sandbox %s: %s", path, exc)


def _unlink(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        _logger.warning("could not remove replay lock %s: %s", path, exc)


def sweep_orphans(runner: ProcessRunner, root: Path | None = None) -> None:
    """Remove sandboxes whose owner is gone, and cf projects whose directory is gone.

    A sandbox with a live lock, such as one in a concurrent ``sq replay`` process, is left
    alone. Never raises; each removal or failed removal is a WARNING.
    """
    sandbox_root = root if root is not None else replays_root()
    _sweep_directories(runner, sandbox_root)
    _sweep_cf_projects(runner)


def _sweep_directories(runner: ProcessRunner, root: Path) -> None:
    if not root.is_dir():
        return
    try:
        entries = sorted(root.iterdir())
    except OSError as exc:
        _logger.warning("could not list replay sandboxes in %s: %s", root, exc)
        return
    for entry in entries:
        if not entry.is_dir():
            continue  # the lock files beside the sandboxes
        lock = _lock_path(root, entry.name)
        if not is_orphan(runner, read_lock(lock)):
            continue
        _logger.warning("removing orphaned replay sandbox %s", entry)
        _remove_tree(entry)
        _unlink(lock)


def _sweep_cf_projects(runner: ProcessRunner) -> None:
    try:
        result = _run(runner, ["cf", "project", "list", "--json"], None)
    except _PROCESS_FAILURES as exc:
        _logger.warning("could not list cf projects to sweep replay sandboxes: %s", exc)
        return
    if result.returncode != 0:
        _logger.warning("could not list cf projects: %s", result.stderr.strip())
        return
    for name in _stale_replay_projects(result.stdout):
        _logger.warning("removing cf project %s: its sandbox directory is gone", name)
        _remove_cf_project(runner, name)


def _stale_replay_projects(listing: str) -> list[str]:
    """Names of ``replay-*`` projects whose recorded path no longer exists."""
    try:
        parsed: object = json.loads(listing)
    except json.JSONDecodeError as exc:
        _logger.warning("could not parse the cf project list: %s", exc)
        return []
    if not isinstance(parsed, list):
        _logger.warning("the cf project list is not a list: %.200r", parsed)
        return []
    stale: list[str] = []
    for item in cast("list[object]", parsed):
        if not isinstance(item, dict):
            continue
        project = cast("dict[str, object]", item)
        name, path = project.get("name"), project.get("projectPath")
        if isinstance(name, str) and name.startswith(CF_PROJECT_PREFIX) and isinstance(path, str):
            if not Path(path).exists():
                stale.append(name)
    return stale
