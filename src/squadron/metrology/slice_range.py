"""Resolve where a slice landed on the target (slice 403, D2 and D3).

A slice lands one of two ways. A merge commit on the target's first-parent line
names it, or the branch was fast-forwarded and only its reflog remembers where it
started. The resolver runs git itself so it can tell a failed git call (``GIT_ERROR``)
from an answer; the shared parsing lives in ``review.git_utils``.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from squadron.metrology.models import ProjectId
from squadron.metrology.slice_range_models import (
    LandingMethod,
    RangeUnresolvedReason,
    SliceLanding,
    SliceRanges,
)
from squadron.metrology.store import MetrologyStore, slice_ranges_record_id
from squadron.review.git_utils import (
    parse_fork_point,
    parse_slice_branch,
    run_git,
    slice_merge_grep_pattern,
)

_logger = logging.getLogger(__name__)

#: ``git merge-base --is-ancestor`` answers "no" with exit 1; both exits are answers.
_IS_ANCESTOR_EXIT_CODES = (0, 1)


class _GitCallFailed(Exception):
    """A git call hung, timed out or exited non-zero; carries the call's name."""

    def __init__(self, call: str) -> None:
        super().__init__(call)
        self.call = call


def _git(repo_root: str, call: str, *args: str, ok_codes: tuple[int, ...] = (0,)) -> tuple[int, str]:
    """Run git; return ``(exit code, stdout)`` or raise ``_GitCallFailed`` naming *call*."""
    result = run_git(list(args), cwd=repo_root)
    if result is None or result.returncode not in ok_codes:
        raise _GitCallFailed(call)
    return result.returncode, result.stdout


def _is_ancestor(repo_root: str, ancestor: str, descendant: str) -> bool:
    code, _ = _git(
        repo_root,
        "merge-base --is-ancestor",
        "merge-base",
        "--is-ancestor",
        ancestor,
        descendant,
        ok_codes=_IS_ANCESTOR_EXIT_CODES,
    )
    return code == 0


def resolve_slice_landings(
    index: int, repo_root: str, target: str
) -> list[SliceLanding] | RangeUnresolvedReason:
    """Every landing of slice *index* on *target*, oldest first, or why there is none.

    A git call that cannot answer returns ``GIT_ERROR`` (WARNING) and stops: none of
    the later paths, and none of the "git answered no" reasons, is tried after it.
    A reason git answered is logged at INFO.
    """
    try:
        outcome = _resolve(index, repo_root, target)
    except _GitCallFailed as failure:
        # Not swallowed: the failure becomes the GIT_ERROR reason plus a WARNING, so the
        # caller reports it and never records an empty range for this slice.
        _logger.warning("Slice %d: git call failed (%s); landings not resolved", index, failure.call)
        return RangeUnresolvedReason.GIT_ERROR
    if isinstance(outcome, RangeUnresolvedReason):
        _logger.info("Slice %d has no landing on %s: %s", index, target, outcome.value)
    return outcome


def _resolve(index: int, repo_root: str, target: str) -> list[SliceLanding] | RangeUnresolvedReason:
    _, listing = _git(
        repo_root,
        "merge search",
        "log",
        "--merges",
        "--first-parent",
        "--reverse",
        "--format=%H",
        "-E",
        f"--grep={slice_merge_grep_pattern(index)}",
        target,
    )
    merges = listing.split()
    if merges:
        return [_merge_landing(repo_root, target, merge) for merge in merges]
    return _fast_forward_landing(index, repo_root, target)


def _merge_landing(repo_root: str, target: str, merge: str) -> SliceLanding:
    """before = M^1, after = M, tip = M^2, fork = merge-base(M^1, M^2) (D3)."""
    _, line = _git(repo_root, "merge parents", "rev-list", "--parents", "-n", "1", merge)
    _merge, before, tip, *_other_parents = line.split()
    _, fork_out = _git(repo_root, "merge-base", "merge-base", before, tip)
    return SliceLanding(
        method=LandingMethod.MERGE_COMMIT,
        target_ref=target,
        before_sha=before,
        after_sha=merge,
        fork_sha=fork_out.strip(),
        tip_sha=tip,
        merge_sha=merge,
        resolved_at=datetime.now(UTC),
    )


def _fast_forward_landing(
    index: int, repo_root: str, target: str
) -> list[SliceLanding] | RangeUnresolvedReason:
    """The ladder for a slice with no merge commit: the branch, then its reflog."""
    _, branches = _git(repo_root, "branch list", "branch", "--list", f"{index}-slice.*")
    branch = parse_slice_branch(branches)
    if branch is None:
        return RangeUnresolvedReason.NO_LANDING
    _, tip_out = _git(repo_root, "rev-parse", "rev-parse", "--verify", f"{branch}^{{commit}}")
    tip = tip_out.strip()
    if not _is_ancestor(repo_root, tip, target):
        return RangeUnresolvedReason.NOT_LANDED
    _, first_parent = _git(repo_root, "first-parent history", "rev-list", "--first-parent", target)
    if tip not in first_parent.split():
        return RangeUnresolvedReason.LANDED_ELSEWHERE
    _, reflog = _git(repo_root, "reflog", "reflog", "show", "--format=%H %gs", branch)
    fork = parse_fork_point(reflog)
    if fork is None:
        return RangeUnresolvedReason.REFLOG_UNAVAILABLE
    if fork == tip:
        return RangeUnresolvedReason.EMPTY_BRANCH
    if not _is_ancestor(repo_root, fork, tip):
        return RangeUnresolvedReason.FORK_NOT_ANCESTOR
    return [
        SliceLanding(
            method=LandingMethod.FAST_FORWARD,
            target_ref=target,
            before_sha=fork,
            after_sha=tip,
            fork_sha=fork,
            tip_sha=tip,
            merge_sha=None,
            resolved_at=datetime.now(UTC),
        )
    ]


@dataclass(frozen=True)
class RecordedLanding:
    """A landing in a slice's range; ``is_new`` when this run added it to the store."""

    landing: SliceLanding
    is_new: bool


@dataclass(frozen=True)
class SliceRangeResult:
    """One slice after recording: its stored-plus-new landings, oldest first.

    ``reason`` is why this run's resolution found nothing (or ``GIT_ERROR``); stored
    landings are still listed beside it, because a stored range outlives its reflog.
    """

    index: int
    landings: list[RecordedLanding]
    reason: RangeUnresolvedReason | None


def record_slice_ranges(
    indices: Sequence[int],
    repo_root: str,
    target: str,
    store: MetrologyStore,
    project_id: ProjectId,
) -> list[SliceRangeResult]:
    """Resolve each slice, persist every landing the store lacks, and report per slice (D1, D4).

    Stored landings are never changed; new ones follow them in resolver order. The store is
    read once up front and written at most once, and only when some slice gained a landing.
    """
    stored = store.get_slice_ranges(project_id)
    stored_slices = stored.slices if stored is not None else {}
    results: list[SliceRangeResult] = []
    gained: dict[int, list[SliceLanding]] = {}
    for index in dict.fromkeys(indices):
        outcome = resolve_slice_landings(index, repo_root, target)
        result, new = _merge_outcome(index, stored_slices.get(index, []), outcome)
        results.append(result)
        if new:
            gained[index] = new
    if gained:
        _persist_gained(store, project_id, stored, gained)
    return results


def _merge_outcome(
    index: int,
    kept: list[SliceLanding],
    outcome: list[SliceLanding] | RangeUnresolvedReason,
) -> tuple[SliceRangeResult, list[SliceLanding]]:
    """Merge a resolution into the stored landings, keyed on ``after_sha``."""
    if isinstance(outcome, RangeUnresolvedReason):
        return SliceRangeResult(index, [RecordedLanding(x, False) for x in kept], outcome), []
    known = {landing.after_sha for landing in kept}
    new = [landing for landing in outcome if landing.after_sha not in known]
    landings = [RecordedLanding(x, False) for x in kept] + [RecordedLanding(x, True) for x in new]
    return SliceRangeResult(index, landings, None), new


def _persist_gained(
    store: MetrologyStore,
    project_id: ProjectId,
    read_at_start: SliceRanges | None,
    gained: dict[int, list[SliceLanding]],
) -> None:
    """Merge new landings into a fresh read of the record and write it once.

    Concurrent runs aren't supported, but a lost write is detected: when the record
    changed since the start read, the merge still keeps both runs' landings and a
    WARNING says so. The window left is the gap between this re-read and the write.
    """
    record_id = slice_ranges_record_id(project_id)
    fresh = store.get_slice_ranges(project_id)
    if fresh != read_at_start:
        _logger.warning(
            "Slice ranges record %s changed during this run; merging into the newer copy", record_id
        )
    slices = {index: list(landings) for index, landings in (fresh.slices if fresh else {}).items()}
    for index, landings in gained.items():
        merged = slices.setdefault(index, [])
        known = {landing.after_sha for landing in merged}
        merged.extend(landing for landing in landings if landing.after_sha not in known)
    store.write_slice_ranges(SliceRanges(record_id=record_id, project_id=project_id, slices=slices))
