"""The ``sq stats slice`` report core: planned effort against what git and run state show (D7).

Read-only. ``history`` must already be loaded (one ``GitHistory.load()`` per invocation);
the only git calls made here are one ``show`` per review artifact version.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from squadron.pipeline.state import RunScan, StateManager
from squadron.review.persistence import REVIEWS_DIR
from squadron.stats.git_history import GitHistory, WindowSource
from squadron.stats.json_support import to_json_dict
from squadron.stats.planning_docs import PlannedSlice, planned_slice, task_file_paths
from squadron.stats.review_rounds import review_rounds, rounds_to_accept
from squadron.stats.slice_spend import SliceSpend, slice_spend
from squadron.stats.task_attribution import (
    GroupStatus,
    SliceWindow,
    TaskGroup,
    attribute,
    implementation_commits,
    post_review_fixups,
    slice_window,
)

#: The row note when a slice has no task file (D9); its groups are simply absent.
NO_TASK_FILE_NOTE = "no task file"
#: Review types reported per slice. "slice" is the slice design review.
DESIGN_REVIEW_TYPE = "slice"
TASKS_REVIEW_TYPE = "tasks"
CODE_REVIEW_TYPE = "code"
REPORTED_REVIEW_TYPES = (DESIGN_REVIEW_TYPE, TASKS_REVIEW_TYPE, CODE_REVIEW_TYPE)


@dataclass(frozen=True)
class ReviewTypeRounds:
    review_type: str
    rounds: int  # committed versions read
    to_accept: int | None  # rounds up to the first accepted one; None if none was accepted


@dataclass(frozen=True)
class GroupRow:
    first_task: int
    last_task: int
    planned_effort: int | None  # sum of the tasks' efforts; None when none states one
    checked: int
    total: int
    status: GroupStatus
    marker_sha: str | None
    extra: int | None
    span: timedelta | None


@dataclass(frozen=True)
class SliceEffortReport:
    index: int
    title: str
    planned_effort: int | None
    window_source: WindowSource
    span: timedelta | None  # first to last window commit, by author date
    implementation_commits: int | None  # None when there is no window
    fixups: int | None
    reviews: tuple[ReviewTypeRounds, ...]
    spend: SliceSpend
    task_file_missing: bool
    groups: tuple[GroupRow, ...]
    markers_not_found: int
    rounds_skipped: int
    lower_bound: bool  # a review's earliest round predates commit-per-round (941)
    unreadable_runs: int

    def to_json_dict(self) -> dict[str, object]:
        return to_json_dict(self)


def slice_effort_report(
    index: int, *, project_root: Path, history: GitHistory, state_manager: StateManager
) -> SliceEffortReport:
    """One slice's effort report; ``UnknownSliceError`` when no plan lists ``index``."""
    planned = planned_slice(index, project_root)
    return build_slice_report(planned, project_root, history, state_manager.scan_runs())


def build_slice_report(
    planned: PlannedSlice, project_root: Path, history: GitHistory, scan: RunScan
) -> SliceEffortReport:
    """The report for a planned slice from an already-scanned run set.

    A rollup reads the plans and scans the runs once, then calls this per slice.
    """
    index = planned.index
    window = slice_window(history, index, task_file_paths(index, project_root))
    groups = () if planned.tasks is None else attribute(window, planned.tasks)
    read = {t: review_rounds(history, index, t) for t in REPORTED_REVIEW_TYPES}
    has_window = window.source is WindowSource.BRANCH
    return SliceEffortReport(
        index=index,
        title=planned.title,
        planned_effort=planned.effort,
        window_source=window.source,
        span=_window_span(window),
        implementation_commits=len(implementation_commits(window)) if has_window else None,
        fixups=len(post_review_fixups(history, index, window)) if has_window else None,
        reviews=tuple(
            ReviewTypeRounds(t, len(r.rounds), rounds_to_accept(r.rounds)) for t, r in read.items()
        ),
        spend=slice_spend(index, scan, project_root / REVIEWS_DIR),
        task_file_missing=planned.tasks is None,
        groups=tuple(_group_row(group) for group in groups),
        markers_not_found=sum(g.status is GroupStatus.MARKER_NOT_FOUND for g in groups),
        rounds_skipped=sum(r.skipped for r in read.values()),
        lower_bound=any(r.lower_bound for r in read.values()),
        unreadable_runs=len(scan.unreadable),
    )


def _window_span(window: SliceWindow) -> timedelta | None:
    if not window.commits:
        return None
    return window.commits[-1].authored_at - window.commits[0].authored_at


def _group_row(group: TaskGroup) -> GroupRow:
    efforts = [t.effort for t in group.tasks if t.effort is not None]
    return GroupRow(
        first_task=group.tasks[0].number,
        last_task=group.tasks[-1].number,
        planned_effort=sum(efforts) if efforts else None,
        checked=sum(t.checked for t in group.tasks),
        total=sum(t.total for t in group.tasks),
        status=group.status,
        marker_sha=group.marker.sha if group.marker else None,
        extra=group.extra,
        span=group.span,
    )
