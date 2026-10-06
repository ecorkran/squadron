"""Git facts the branch and commit actions share (slice 196 D5, D6, D8).

Reads here are strict: a write operation never degrades to a guess. Every git
call goes through ``review.git_utils.run_git``, which is bounded by a timeout and
returns ``None`` when git could not answer.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Protocol

from squadron.integrations.context_forge import ContextForgeError, ContextForgeNotAvailable
from squadron.review.git_utils import DEFAULT_DIFF_BASE, INTEGRATION_BRANCH_KEY, run_git

_logger = logging.getLogger(__name__)

# Output of ``git branch --show-current`` is empty when HEAD is detached.
_DETACHED_HEAD = "(detached HEAD)"


class ConfigReader(Protocol):
    """The one cf capability the target reader needs (``ContextForgeClient`` satisfies it)."""

    def get_config(self, key: str) -> str: ...


class GitEnvironmentError(Exception):
    """The git environment cannot support the operation, for this item and every later one.

    Ends the run (it propagates out of ``execute_pipeline``) rather than flagging one item.
    """


class GitStateUnknownError(GitEnvironmentError):
    """Git may have left the repository mid-operation; nothing can safely build on it."""


class NoDesignFileError(ValueError):
    """A slice has no design file, so its branch cannot be named (an item failure)."""


class SliceNotInPlanError(ValueError):
    """cf's current slice plan has no slice with this index (an item failure)."""


def parse_slice_index(raw: object) -> int:
    """A slice index from a param, which arrives as an int or its string form.

    Raises ``ValueError`` when it is anything else (for example a whole ``each`` record).
    """
    try:
        return int(str(raw))
    except ValueError:
        raise ValueError(f"expected a slice index, got {raw!r}") from None


def read_integration_target(cf_client: ConfigReader) -> str:
    """The branch that slice branches fork from and merge into.

    Unset means ``DEFAULT_DIFF_BASE``. Unlike ``resolve_diff_base``, a cf failure
    raises: degrading to ``main`` is wrong for an operation that writes history.
    """
    try:
        value = str(cf_client.get_config(INTEGRATION_BRANCH_KEY)).strip()
    except (ContextForgeNotAvailable, ContextForgeError) as exc:
        _logger.exception("cannot read %s from cf", INTEGRATION_BRANCH_KEY)
        raise GitEnvironmentError(
            f"cannot read {INTEGRATION_BRANCH_KEY} from cf: {exc}. "
            "Refusing to guess the integration target."
        ) from exc
    return value or DEFAULT_DIFF_BASE


def slice_branch_name(index: int, design_file: str | None) -> str:
    """``{index}-slice.{name}``, where name is the design file's stem without its prefix."""
    if not design_file:
        raise NoDesignFileError(f"slice {index} has no design file; cannot name its branch")
    stem = Path(design_file).stem
    prefix = f"{index}-slice."
    return stem if stem.startswith(prefix) else f"{prefix}{stem}"


def current_branch(cwd: str) -> str:
    """The checked-out branch, or ``(detached HEAD)``; raises when git cannot say."""
    result = run_git(["branch", "--show-current"], cwd=cwd)
    if result is None or result.returncode != 0:
        raise GitEnvironmentError(f"cannot read the current branch: {_failure_text(result)}")
    return result.stdout.strip() or _DETACHED_HEAD


def verify_git_state(expected_branch: str, *, cwd: str) -> None:
    """Raise ``GitStateUnknownError`` unless the repository is demonstrably settled.

    Passes only when all three reads succeed: no ``MERGE_HEAD``, the current branch
    is ``expected_branch``, and no tracked changes. A failed or timed-out read counts
    as a failure, because an unreadable state is an unknown state.
    """
    problems: list[str] = []

    merge_head = run_git(["rev-parse", "-q", "--verify", "MERGE_HEAD"], cwd=cwd)
    if merge_head is None:
        problems.append("MERGE_HEAD read failed: git timed out or could not run")
    elif merge_head.returncode == 0:
        problems.append("MERGE_HEAD present")
    elif merge_head.returncode != 1:  # -q --verify exits 1 when the ref is simply absent
        problems.append(f"MERGE_HEAD read failed: {merge_head.stderr.strip()}")

    branch = run_git(["branch", "--show-current"], cwd=cwd)
    if branch is None or branch.returncode != 0:
        problems.append(f"current branch read failed: {_failure_text(branch)}")
    else:
        current = branch.stdout.strip() or _DETACHED_HEAD
        if current != expected_branch:
            problems.append(f"on {current}, expected {expected_branch}")

    status = run_git(["status", "--porcelain", "--untracked-files=no"], cwd=cwd)
    if status is None or status.returncode != 0:
        problems.append(f"status read failed: {_failure_text(status)}")
    elif status.stdout.strip():
        problems.append(f"tracked changes: {_changed_paths(status.stdout)}")

    if problems:
        message = f"git state unverified (expected {expected_branch}): " + "; ".join(problems)
        _logger.error(message)
        raise GitStateUnknownError(message)


def branch_work_count(branch: str, target: str, *, cwd: str) -> int:
    """Commits of the branch's own that the target lacks, merge commits excluded (197 D4, D5).

    A catch-up merge alone is not work. A failed or timed-out count raises
    ``GitStateUnknownError``: a guessed 0 would reimplement over existing work.
    """
    return _rev_count(
        ["rev-list", "--count", "--no-merges", f"{target}..{branch}"],
        cwd,
        f"cannot count work on {branch}",
    )


def branch_behind_count(branch: str, target: str, *, cwd: str) -> int:
    """Commits on the target that the branch lacks, merges included (197 D5)."""
    return _rev_count(
        ["rev-list", "--count", f"{branch}..{target}"],
        cwd,
        f"cannot compare {branch} with {target}",
    )


def _rev_count(args: list[str], cwd: str, failure: str) -> int:
    result = run_git(args, cwd=cwd)
    if result is None or result.returncode != 0:
        message = f"{failure}: {_failure_text(result)}"
        _logger.error(message)
        raise GitStateUnknownError(message)
    return int(result.stdout.strip())


def _failure_text(result: subprocess.CompletedProcess[str] | None) -> str:
    """git's stderr for a refused command, or the timeout text when git never answered."""
    if result is not None and result.stderr.strip():
        return result.stderr.strip()
    return "git timed out or could not run"


def _changed_paths(porcelain: str) -> str:
    """The paths from ``git status --porcelain`` output, comma separated."""
    return ", ".join(line[3:] for line in porcelain.splitlines() if line.strip())
