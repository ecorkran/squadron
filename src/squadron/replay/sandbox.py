"""A history-free sandbox repository for one producer replay (slice 177 D3).

The repository itself is a ``HistoryFreeSandbox`` (one commit, no later history). This
adds the replay branch and registers the sandbox with cf as ``replay-<replay_id>``, because
cf resolves the project from the cwd and ``P4``/``P5`` run cf operations; it is removed on
exit.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from pathlib import Path
from types import TracebackType
from typing import Self, cast

from squadron.core.process_lock import is_orphan, read_lock
from squadron.core.process_runner import ProcessRunner
from squadron.replay.history_free_sandbox import (
    LOCK_SUFFIX,
    PROCESS_FAILURES,
    SANDBOX_COMMAND_TIMEOUT_SECONDS,
    HistoryFreeSandbox,
    SandboxError,
    lock_path,
    remove_tree,
    run_command,
    unlink_quietly,
)
from squadron.stats.planning_docs import UnknownSliceError, plan_file_for

__all__ = [
    "LOCK_SUFFIX",
    "SANDBOX_COMMAND_TIMEOUT_SECONDS",
    "ReplaySandbox",
    "SandboxError",
    "replays_root",
    "sweep_orphans",
]

_logger = logging.getLogger(__name__)

#: A sandbox's cf project is ``CF_PROJECT_PREFIX`` + its replay id.
CF_PROJECT_PREFIX = "replay-"
BRANCH_PREFIX = "replay/"


def replays_root() -> Path:
    """``~/.config/squadron/replays/`` — sibling of the PR-review ``worktrees`` directory."""
    return Path.home() / ".config" / "squadron" / "replays"


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
        self._slice_index = slice_index
        self._runner = runner
        self._repository = HistoryFreeSandbox(
            start_sha=start_sha,
            sandbox_id=replay_id,
            repo_root=repo_root,
            runner=runner,
            root=root if root is not None else replays_root(),
        )
        self._registered = False
        self._kept = False

    @property
    def path(self) -> Path:
        return self._repository.path

    @property
    def cf_project(self) -> str:
        return f"{CF_PROJECT_PREFIX}{self._replay_id}"

    @property
    def branch(self) -> str:
        return f"{BRANCH_PREFIX}{self._replay_id}"

    def keep(self) -> None:
        """Leave the sandbox in place on exit (the runner keeps it when a store write fails)."""
        self._repository.keep()
        self._kept = True

    def __enter__(self) -> Self:
        self._repository.__enter__()
        built = False
        try:
            self._repository.checked("git", "-C", str(self.path), "switch", "-q", "-c", self.branch)
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
            self._remove_cf_registration()  # before the directory, as cf reads its path
        self._repository.__exit__(exc_type, exc, tb)

    def _register_with_cf(self) -> None:
        """Register the sandbox as a cf project and point cf at the slice's initiative.

        The branch guard compares the checkout to ``git.integration_branch``, so the sandbox
        branch is set as its integration branch; and a fresh cf project has no slice plan, so
        ``cf set arch`` names the initiative whose plan lists the slice (Task 1 spike).
        """
        initiative = self._initiative()
        checked = self._repository.checked
        checked("cf", "init", "--lite", "--no-ide", "--name", self.cf_project, cwd=self.path)
        self._registered = True
        checked("cf", "config", "set", "git.integration_branch", self.branch, cwd=self.path)
        checked("cf", "set", "arch", initiative, cwd=self.path)

    def _initiative(self) -> str:
        """The initiative index of the slice plan listing the slice, at the start point."""
        try:
            plan = plan_file_for(self._slice_index, self.path)
        except UnknownSliceError as exc:
            raise SandboxError(
                f"slice {self._slice_index} is in no slice plan at start commit {self._start_sha}"
            ) from exc
        return plan.name.split("-", 1)[0]

    def _cleanup(self) -> None:
        """Remove the cf project, the directory, then the lock. Never raises."""
        self._remove_cf_registration()
        self._repository.cleanup()

    def _remove_cf_registration(self) -> None:
        if self._registered:
            _remove_cf_project(self._runner, self.cf_project)
            self._registered = False


def _remove_cf_project(runner: ProcessRunner, name: str) -> None:
    try:
        result = run_command(runner, ["cf", "project", "rm", name, "--yes"], None)
    except PROCESS_FAILURES as exc:
        _logger.warning("could not remove cf project %s: %s", name, exc)
        return
    if result.returncode != 0:
        _logger.warning("could not remove cf project %s: %s", name, result.stderr.strip())


def sweep_orphans(
    runner: ProcessRunner,
    root: Path | None = None,
    *,
    sweep_cf_projects: bool = True,
    sibling_suffixes: Sequence[str] = (),
) -> None:
    """Remove sandboxes whose owner is gone, and cf projects whose directory is gone.

    A sandbox with a live lock, such as one in a concurrent ``sq replay`` process, is left
    alone. Never raises; each removal or failed removal is a WARNING.

    The keyword-only parameters default to ``sq replay``'s behavior. The benchmark sandbox
    passes ``sweep_cf_projects=False`` (it registers no cf project) and its sibling
    suffixes (``.home``, ``.out``): directories that have no lock of their own and go with
    their owner.
    """
    sandbox_root = root if root is not None else replays_root()
    _sweep_directories(runner, sandbox_root, tuple(sibling_suffixes))
    if sweep_cf_projects:
        _sweep_cf_projects(runner)


def _sweep_directories(runner: ProcessRunner, root: Path, sibling_suffixes: tuple[str, ...]) -> None:
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
        if entry.name.endswith(sibling_suffixes):
            continue  # a sibling directory: removed with its owner below
        lock = lock_path(root, entry.name)
        if not is_orphan(runner, read_lock(lock)):
            continue
        _logger.warning("removing orphaned replay sandbox %s", entry)
        remove_tree(entry)
        for suffix in sibling_suffixes:
            remove_tree(root / f"{entry.name}{suffix}")
        unlink_quietly(lock)


def _sweep_cf_projects(runner: ProcessRunner) -> None:
    try:
        result = run_command(runner, ["cf", "project", "list", "--json"], None)
    except PROCESS_FAILURES as exc:
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
