"""Slice candidates from the stored ``slice_ranges`` record (slice 426 D1, D2, D4).

Every slice index in the record leaves discovery exactly once: as a candidate, as a
rejection that names the rule, or as a harness failure (a git query that did not answer).
Only git answers become rejections.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from squadron.benchmark.build_errors import halt
from squadron.benchmark.diff_normalize import is_dropped
from squadron.benchmark.slice_git import SliceHarnessError, run_git
from squadron.core.process_runner import ProcessRunner
from squadron.metrology.project_id import ProjectId
from squadron.metrology.slice_case_models import SliceCandidateRejection
from squadron.metrology.slice_range_models import SliceLanding, SliceRanges

_logger = logging.getLogger(__name__)

SLICE_RANGES_COMMAND = "sq metrology slice-ranges"
_NAME_STATUS_ARGS = ("diff", "--name-status", "-z")
#: ``git diff --name-status`` statuses that name two paths (old, then new).
_TWO_PATH_STATUSES = ("R", "C")


class SliceRangeSource(Protocol):
    def get_slice_ranges(self, project_id: ProjectId) -> SliceRanges | None: ...


@dataclass(frozen=True)
class SliceCandidate:
    """A slice with exactly one landing, ready for qualification."""

    project_id: ProjectId
    slice_index: int
    landing: SliceLanding


@dataclass(frozen=True)
class SliceRejection:
    """A slice that is not a case, and why. ``landing`` is the one the record is keyed by
    (the newest, for a slice with several)."""

    slice_index: int
    rejection: SliceCandidateRejection
    detail: str
    landing: SliceLanding


@dataclass(frozen=True)
class SliceHarnessFailure:
    """A slice whose discovery check could not run; recorded as ``harness_error``."""

    slice_index: int
    detail: str
    landing: SliceLanding


@dataclass(frozen=True)
class DiscoveryResult:
    candidates: tuple[SliceCandidate, ...]
    rejections: tuple[SliceRejection, ...]
    harness_failures: tuple[SliceHarnessFailure, ...]


def discover(
    store: SliceRangeSource,
    project_id: ProjectId,
    runner: ProcessRunner,
    repo: Path,
    timeout_s: float,
) -> DiscoveryResult:
    """Sort every slice in the project's ``slice_ranges`` record into the three outcomes."""
    ranges = store.get_slice_ranges(project_id)
    if ranges is None:
        raise halt(f"no slice ranges are recorded for this project; run `{SLICE_RANGES_COMMAND}` first")
    candidates: list[SliceCandidate] = []
    rejections: list[SliceRejection] = []
    failures: list[SliceHarnessFailure] = []
    for index in sorted(ranges.slices):
        landings = ranges.slices[index]
        newest = landings[-1]
        if len(landings) > 1:
            shas = ", ".join(landing.after_sha[:12] for landing in landings)
            detail = f"{len(landings)} landings: {shas}"
            rejections.append(
                SliceRejection(index, SliceCandidateRejection.MULTIPLE_LANDINGS, detail, newest)
            )
            continue
        try:
            merges = _merges_on_branch(runner, repo, newest, timeout_s)
        except SliceHarnessError as exc:
            failures.append(SliceHarnessFailure(index, str(exc), newest))
            continue
        if merges:
            detail = f"merge commits on the branch: {', '.join(sha[:12] for sha in merges)}"
            rejections.append(
                SliceRejection(index, SliceCandidateRejection.BRANCH_CONTAINS_MERGES, detail, newest)
            )
        else:
            candidates.append(SliceCandidate(project_id, index, newest))
    return DiscoveryResult(tuple(candidates), tuple(rejections), tuple(failures))


def _merges_on_branch(
    runner: ProcessRunner, repo: Path, landing: SliceLanding, timeout_s: float
) -> list[str]:
    """Merge commits in ``fork..tip``: the target merged into the branch puts unrelated work in
    the reference diff (D2)."""
    out = run_git(
        runner,
        repo,
        ("rev-list", "--merges", f"{landing.fork_sha}..{landing.tip_sha}"),
        timeout_s,
    )
    return out.split()


def has_code_change(
    fork_sha: str, tip_sha: str, repo: Path, runner: ProcessRunner, timeout_s: float
) -> bool:
    """True unless every path in ``fork..tip`` is one diff normalization drops (D4).

    Both sides of a rename are considered, so a rename from a dropped path to a code path
    counts as code. A failed ``git`` raises ``SliceHarnessError``.
    """
    out = run_git(runner, repo, (*_NAME_STATUS_ARGS, fork_sha, tip_sha), timeout_s)
    return any(not is_dropped(path) for path in _changed_paths(out))


def _changed_paths(name_status_z: str) -> list[str]:
    """Every path in ``git diff --name-status -z`` output: a status, then one or two paths."""
    fields = [field for field in name_status_z.split("\0") if field]
    paths: list[str] = []
    index = 0
    while index < len(fields):
        count = 2 if fields[index].startswith(_TWO_PATH_STATUSES) else 1
        paths.extend(fields[index + 1 : index + 1 + count])
        index += 1 + count
    return paths
