"""Choosing and deleting dead run-state files for ``sq runs prune`` (slice 174 D9).

``plan_prune`` is pure apart from the injected definition loader and liveness
check: it selects runs by category, run-id and filters, then applies the
protection rules. ``apply_prune`` deletes what a plan names and nothing else.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from pathlib import Path

from squadron.pipeline.batch_report import report_sibling_paths
from squadron.pipeline.executor import ExecutionStatus
from squadron.pipeline.run_listing import DefinitionCache, DefinitionLoader
from squadron.pipeline.run_liveness import LivenessAssessment, RunLiveness
from squadron.pipeline.state import RunScan, RunState, UnreadableRun, state_file_name

_logger = logging.getLogger(__name__)


class PruneCategory(StrEnum):
    FAILED = "failed"
    ORPHANED = "orphaned"
    STALE = "stale"
    UNAVAILABLE = "unavailable"
    UNREADABLE = "unreadable"
    UNSUPPORTED_SCHEMA = "unsupported-schema"
    COMPLETED = "completed"
    PAUSED = "paused"
    UNOWNED = "unowned"


# Selected when no --status is given. STALE is never here (D3).
DEFAULT_CATEGORIES = frozenset(
    {
        PruneCategory.FAILED,
        PruneCategory.ORPHANED,
        PruneCategory.UNAVAILABLE,
        PruneCategory.UNREADABLE,
    }
)

# A run in one of these is pruned only when named, or when every one of them it
# matches was asked for by --status, even if another selected category matches too.
PROTECTED_CATEGORIES = frozenset(
    {PruneCategory.PAUSED, PruneCategory.UNOWNED, PruneCategory.STALE, PruneCategory.UNSUPPORTED_SCHEMA}
)

_STATUS_CATEGORIES: dict[str, PruneCategory] = {
    ExecutionStatus.FAILED.value: PruneCategory.FAILED,
    ExecutionStatus.COMPLETED.value: PruneCategory.COMPLETED,
    ExecutionStatus.PAUSED.value: PruneCategory.PAUSED,
}

_LIVENESS_CATEGORIES: dict[RunLiveness, PruneCategory] = {
    RunLiveness.ORPHANED: PruneCategory.ORPHANED,
    RunLiveness.STALE: PruneCategory.STALE,
    RunLiveness.UNOWNED: PruneCategory.UNOWNED,
}

LivenessCheck = Callable[[RunState], LivenessAssessment | None]


class PruneUsageError(ValueError):
    """The selection asked for is contradictory; the CLI exits 2."""


@dataclass(frozen=True)
class PruneCandidate:
    run_id: str
    pipeline: str | None  # None for unreadable
    status: str | None  # None for unreadable
    categories: frozenset[PruneCategory]
    age: timedelta | None  # None when an unreadable file's mtime is unknown
    path: Path


@dataclass(frozen=True)
class PruneRefusal:
    run_id: str
    reason: str


@dataclass(frozen=True)
class PrunePlan:
    candidates: list[PruneCandidate]
    refusals: list[PruneRefusal]


@dataclass(frozen=True)
class _Considered:
    """One run before selection: its candidate shape, and whether it is live."""

    candidate: PruneCandidate
    live: bool


def plan_prune(
    scan: RunScan,
    *,
    runs_dir: Path,
    statuses: frozenset[PruneCategory] | None,
    run_ids: Iterable[str],
    pipeline: str | None,
    older_than: timedelta | None,
    now: datetime,
    load_definition: DefinitionLoader,
    assess: LivenessCheck,
) -> PrunePlan:
    """Select runs to prune (D9): categories or run-ids, filters, then protection."""
    named = set(run_ids)
    if named and statuses is not None:
        raise PruneUsageError("name runs or select --status categories, not both")
    selected = DEFAULT_CATEGORIES if statuses is None else statuses
    definitions = DefinitionCache(load_definition)
    considered = [_consider(state, runs_dir, now, definitions, assess) for state in scan.states] + [
        _consider_unreadable(entry, now) for entry in scan.unreadable
    ]
    candidates: list[PruneCandidate] = []
    refusals: list[PruneRefusal] = []
    for item in considered:
        run = item.candidate
        if named:
            if run.run_id not in named:
                continue
        elif not run.categories & selected:
            continue
        if item.live:
            if named:
                refusals.append(PruneRefusal(run.run_id, "run is live; not pruned"))
            continue
        if not named and not _protection_allows(run.categories, selected):
            continue
        if _filtered_out(run, pipeline, older_than):
            continue
        candidates.append(run)
    found = {item.candidate.run_id for item in considered}
    refusals.extend(PruneRefusal(run_id, "no such run") for run_id in sorted(named - found))
    candidates.sort(key=lambda c: c.run_id)
    return PrunePlan(candidates, refusals)


def _protection_allows(
    categories: frozenset[PruneCategory], selected: frozenset[PruneCategory]
) -> bool:
    """The single protection rule: every protected category a run has was selected."""
    return (categories & PROTECTED_CATEGORIES) <= selected


def _filtered_out(run: PruneCandidate, pipeline: str | None, older_than: timedelta | None) -> bool:
    if pipeline is not None and run.pipeline != pipeline.lower():
        return True  # unreadable files have no pipeline, so a --pipeline excludes them
    if older_than is not None and (run.age is None or run.age < older_than):
        return True
    return False


def _consider(
    state: RunState,
    runs_dir: Path,
    now: datetime,
    definitions: DefinitionCache,
    assess: LivenessCheck,
) -> _Considered:
    categories: set[PruneCategory] = set()
    if (status_category := _STATUS_CATEGORIES.get(state.status)) is not None:
        categories.add(status_category)
    assessment = assess(state)
    live = assessment is not None and assessment.liveness is RunLiveness.LIVE
    if assessment is not None and assessment.liveness in _LIVENESS_CATEGORIES:
        categories.add(_LIVENESS_CATEGORIES[assessment.liveness])
    if not live and definitions.get(state) is None:
        categories.add(PruneCategory.UNAVAILABLE)
    candidate = PruneCandidate(
        run_id=state.run_id,
        pipeline=state.pipeline,
        status=state.status,
        categories=frozenset(categories),
        age=now - state.updated_at,
        path=runs_dir / state_file_name(state.run_id),
    )
    return _Considered(candidate, live)


def _consider_unreadable(entry: UnreadableRun, now: datetime) -> _Considered:
    candidate = PruneCandidate(
        run_id=entry.run_id,
        pipeline=None,
        status=None,
        categories=frozenset(
            {PruneCategory.UNSUPPORTED_SCHEMA if entry.unsupported_schema else PruneCategory.UNREADABLE}
        ),
        age=None if entry.mtime is None else now - entry.mtime,
        path=entry.path,
    )
    return _Considered(candidate, live=False)


@dataclass(frozen=True)
class PruneResult:
    removed: int  # runs whose state file is gone after the call
    failed: int  # runs with at least one file that could not be deleted


def apply_prune(plan: PrunePlan, runs_dir: Path) -> PruneResult:
    """Delete each candidate's state file and its report siblings (D9).

    Only paths inside *runs_dir* are touched. A file already gone counts as
    removed; any other ``OSError`` is logged at ERROR with the path and the
    rest of the plan still runs.
    """
    root = runs_dir.resolve()
    removed = failed = 0
    for candidate in plan.candidates:
        paths = [candidate.path, *report_sibling_paths(runs_dir, candidate.run_id)]
        deleted = [_delete(path, root) for path in paths]  # attempt every file
        if all(deleted):
            removed += 1
        else:
            failed += 1
    return PruneResult(removed, failed)


def _delete(path: Path, root: Path) -> bool:
    if not path.resolve().is_relative_to(root):
        _logger.error("prune: refusing to delete %s: outside the runs directory %s", path, root)
        return False
    try:
        path.unlink()
    except FileNotFoundError:
        return True  # already gone: the goal state
    except OSError:
        # One undeletable file must not stop the rest of the prune; the caller
        # counts it and the command exits 1.
        _logger.exception("prune: cannot delete %s", path)
        return False
    return True


_DURATION_UNITS: dict[str, timedelta] = {
    "s": timedelta(seconds=1),
    "m": timedelta(minutes=1),
    "h": timedelta(hours=1),
    "d": timedelta(days=1),
    "w": timedelta(weeks=1),
}
DURATION_FORM = "<int><unit>, unit one of s m h d w (e.g. 7d)"
_DURATION_RE = re.compile(r"^\s*(\d+)\s*([a-z])\s*$")


def parse_duration(text: str) -> timedelta:
    """Parse ``--older-than``: ``<int><unit>``, lenient on case and whitespace."""
    match = _DURATION_RE.match(text.lower())
    if match is None or match.group(2) not in _DURATION_UNITS:
        raise ValueError(f"invalid duration {text!r}: expected {DURATION_FORM}")
    return int(match.group(1)) * _DURATION_UNITS[match.group(2)]
