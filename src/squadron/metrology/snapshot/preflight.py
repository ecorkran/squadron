"""Preflight and integrity checks for a code snapshot (D9, D10).

A snapshot measures a clean HEAD, read-only. ``preflight`` refuses anything else
before a tool runs; ``check_integrity`` reruns the same tree check afterwards so a
tool that wrote into the repo is caught and nothing is recorded.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from squadron.config.manager import get_config, get_positive_int_config
from squadron.metrology.errors import (
    MetrologyError,
    SnapshotIntegrityError,
    SnapshotPreflightError,
)
from squadron.metrology.snapshot.coverage import KEY_COVERAGE_REPORT, parse_report_path
from squadron.metrology.snapshot_models import LengthLimits
from squadron.review.git_utils import run_git

_logger = logging.getLogger(__name__)

KEY_MAX_FILE_LINES = "metrology.max_file_lines"
KEY_MAX_FUNCTION_LINES = "metrology.max_function_lines"
KEY_SNAPSHOT_EXCLUDE = "metrology.snapshot_exclude"
KEY_TOOL_TIMEOUT = "metrology.snapshot_tool_timeout_s"

#: The one untracked file a clean tree may contain: squadron reads it, no measured
#: tool does, and its values are recorded on the snapshot (D9).
EXEMPT_UNTRACKED_PATH = ".squadron.toml"

#: ``git status --porcelain -z`` marks untracked entries with this status code.
_UNTRACKED_STATUS = "??"
#: Rename and copy entries are followed by a second NUL-separated path.
_PAIRED_STATUS_CODES = frozenset("RC")


@dataclass(frozen=True)
class PreflightResult:
    """What a passing preflight hands to the orchestrator."""

    head_sha: str
    limits: LengthLimits
    project_exclusions: tuple[str, ...]
    tool_timeout_s: int


def _git_stdout(repo_root: Path, args: list[str], error: type[MetrologyError]) -> str | None:
    """Run git; return stdout, or None when git ran and refused (non-zero exit).

    git being unable to answer at all is never a clean answer: it logs ERROR naming
    the call and raises *error*.
    """
    call = "git " + " ".join(args)
    completed = run_git(args, cwd=str(repo_root))
    if completed is None:
        _logger.error("%s returned no result in %s", call, repo_root)
        raise error(
            f"`{call}` could not be run in {repo_root}. "
            "Check that git is installed and the directory exists."
        )
    if completed.returncode != 0:
        return None
    return completed.stdout


def _dirty_paths(repo_root: Path, error: type[MetrologyError]) -> list[str]:
    """Paths reported by ``git status``, less the one exempt untracked file."""
    call = ["status", "--porcelain", "-z", "--untracked-files=all"]
    stdout = _git_stdout(repo_root, call, error)
    if stdout is None:
        _logger.error("git %s failed in %s", " ".join(call), repo_root)
        raise error(
            f"`git {' '.join(call)}` failed in {repo_root}; "
            "run it by hand to see why, then re-run `sq metrology snapshot`."
        )
    entries = [entry for entry in stdout.split("\0") if entry]
    paths: list[str] = []
    skip_next = False
    for entry in entries:
        if skip_next:
            skip_next = False
            continue
        status, path = entry[:2], entry[3:]
        if status[0] in _PAIRED_STATUS_CODES or status[1] in _PAIRED_STATUS_CODES:
            skip_next = True
        if status == _UNTRACKED_STATUS and path == EXEMPT_UNTRACKED_PATH:
            continue
        paths.append(path)
    return paths


def _read_limit(key: str, repo_root: Path) -> int | None:
    value = get_config(key, cwd=str(repo_root))
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise SnapshotPreflightError(
            f"{key} must be a positive integer, got {value!r}. "
            f"Fix it with `sq config set {key} <lines> --project`."
        )
    return value


def _read_exclusions(repo_root: Path) -> tuple[str, ...]:
    raw = get_config(KEY_SNAPSHOT_EXCLUDE, cwd=str(repo_root))
    if raw is None:
        return ()
    if not isinstance(raw, str):
        raise SnapshotPreflightError(
            f"{KEY_SNAPSHOT_EXCLUDE} must be a comma-separated string, got {raw!r}."
        )
    return tuple(pattern.strip() for pattern in raw.split(",") if pattern.strip())


def _read_timeout(repo_root: Path) -> int:
    try:
        return get_positive_int_config(KEY_TOOL_TIMEOUT, cwd=str(repo_root))
    except ValueError as exc:
        raise SnapshotPreflightError(
            f"{exc}. Fix it with `sq config set {KEY_TOOL_TIMEOUT} <seconds> --project`."
        ) from exc


def _head_sha(repo_root: Path) -> str:
    toplevel = _git_stdout(repo_root, ["rev-parse", "--show-toplevel"], SnapshotPreflightError)
    if toplevel is None:
        raise SnapshotPreflightError(
            f"{repo_root} is not a git repository. Run `sq metrology snapshot --cwd` "
            "on a repository root."
        )
    if Path(toplevel.strip()).resolve() != repo_root.resolve():
        raise SnapshotPreflightError(
            f"{repo_root} is inside a repository but is not its root ({toplevel.strip()}). "
            "Run `sq metrology snapshot --cwd` on the repository root."
        )
    head = _git_stdout(repo_root, ["rev-parse", "HEAD"], SnapshotPreflightError)
    if head is None or not head.strip():
        raise SnapshotPreflightError(
            f"{repo_root} has no commits, so there is no HEAD to measure. Make a commit first."
        )
    return head.strip()


def preflight(repo_root: Path) -> PreflightResult:
    """Validate that *repo_root* is a clean git checkout with valid snapshot config."""
    head_sha = _head_sha(repo_root)
    dirty = _dirty_paths(repo_root, SnapshotPreflightError)
    if dirty:
        raise SnapshotPreflightError(
            f"The working tree is not clean: {', '.join(sorted(dirty))}. "
            "Commit, stash or remove these paths, then re-run `sq metrology snapshot`."
        )
    max_file = _read_limit(KEY_MAX_FILE_LINES, repo_root)
    max_function = _read_limit(KEY_MAX_FUNCTION_LINES, repo_root)
    # Validated here so a bad value fails before any tool runs; the reader resolves the
    # key again at measurement time (401 D6).
    parse_report_path(get_config(KEY_COVERAGE_REPORT, cwd=str(repo_root)))
    limits = LengthLimits(
        max_file_lines=max_file,
        max_function_lines=max_function,
        limits_declared=max_file is not None or max_function is not None,
    )
    return PreflightResult(
        head_sha=head_sha,
        limits=limits,
        project_exclusions=_read_exclusions(repo_root),
        tool_timeout_s=_read_timeout(repo_root),
    )


def check_integrity(repo_root: Path) -> None:
    """Rerun the clean-tree check after measuring; raise if the repo changed.

    Prevention is the guarantee (every tool runs read-only); this catches a tool
    that wrote a tracked or untracked file anyway. Ignored paths aren't checked.
    """
    dirty = _dirty_paths(repo_root, SnapshotIntegrityError)
    if dirty:
        raise SnapshotIntegrityError(
            f"The repo changed while measuring: {', '.join(sorted(dirty))}. "
            "A measurement tool wrote into the repository; no snapshot was recorded. "
            "Restore the paths with git and report the tool."
        )
