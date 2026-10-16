"""Slice window and task attribution from the in-memory commit graph (slice 176 D5).

No git calls here: everything reads the graph ``GitHistory.load()`` built. Code commits
do not cite task numbers, so a task file's prescribed commit subjects are the anchors.
The exact-match rule is deliberate (see D5): a reworded subject shows up as
``marker not found`` and is counted, never silently misattributed.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from pathlib import Path

from squadron.integrations.context_forge import DOCS_ROOT
from squadron.review.persistence import REVIEWS_DIR, TASKS_DIR
from squadron.stats.git_history import Commit, GitHistory, WindowSource
from squadron.stats.planning_docs import PlannedTask

_logger = logging.getLogger(__name__)


class GroupStatus(StrEnum):
    ATTRIBUTED = "attributed"
    MARKER_NOT_FOUND = "marker not found"
    UNMARKED = "unmarked"  # trailing tasks that prescribe no commit subject
    UNAVAILABLE = "unavailable"  # no window, or no task prescribes a subject


@dataclass(frozen=True)
class SliceWindow:
    source: WindowSource
    commits: tuple[Commit, ...]  # oldest first; empty when the source is NONE


@dataclass(frozen=True)
class TaskGroup:
    tasks: tuple[PlannedTask, ...]
    status: GroupStatus
    marker: Commit | None  # the group's last matched marker commit
    extra: int | None  # window commits in the group that are not markers
    span: timedelta | None  # author-date time from the previous marker to this one


def slice_window(history: GitHistory, index: int, task_paths: Sequence[Path]) -> SliceWindow:
    """The branch tip's first-parent chain back to (not including) the task file's commit."""
    none = SliceWindow(source=WindowSource.NONE, commits=())
    tip = history.branch_tip(index)
    if tip is None or not task_paths:
        return none
    added = [
        commit
        for path in task_paths
        if (commit := history.first_added(f"{TASKS_DIR}/{path.name}")) is not None
    ]
    if not added:
        _logger.warning("slice %d: no commit adds its task file; no commit window", index)
        return none
    start = min(added, key=lambda commit: commit.authored_at)
    commits: list[Commit] = []
    for commit in history.first_parent_chain(tip):
        if commit.sha == start.sha:
            return SliceWindow(source=WindowSource.BRANCH, commits=tuple(reversed(commits)))
        commits.append(commit)
    _logger.warning(
        "slice %d: its task file's commit %s is not on the branch's first-parent chain; "
        "no commit window",
        index,
        start.sha,
    )
    return none


def implementation_commits(window: SliceWindow) -> tuple[Commit, ...]:
    """Window commits touching any path outside ``project-documents/`` (D5 rule 4)."""
    prefix = f"{DOCS_ROOT}/"
    return tuple(
        commit
        for commit in window.commits
        if any(not change.path.startswith(prefix) for change in commit.changes)
    )


def post_review_fixups(history: GitHistory, index: int, window: SliceWindow) -> tuple[Commit, ...]:
    """Implementation commits authored after the code review artifact first appeared (rule 5)."""
    review = history.first_added(f"{REVIEWS_DIR}/{index}-review.code.*.md")
    if review is None:
        return ()
    return tuple(
        commit for commit in implementation_commits(window) if commit.authored_at > review.authored_at
    )


def attribute(window: SliceWindow, tasks: Sequence[PlannedTask]) -> tuple[TaskGroup, ...]:
    """Group ``tasks`` by their prescribed commit subjects (D5 rules 1–2).

    A group runs from the task after the previous marker task through its own marker task.
    A task that prescribes several subjects ends its group at the latest one found; the
    group is ``marker not found`` only when none of its subjects is in the window. When a
    group's marker is missing, the next group's commits start after the last marker that
    was found, so the missing group's commits count as that next group's extras.
    """
    if not tasks:
        return ()
    anchored = [task for task in tasks if task.commit_subjects]
    if window.source is WindowSource.NONE or not anchored:
        return (TaskGroup(tuple(tasks), GroupStatus.UNAVAILABLE, None, None, None),)
    groups: list[TaskGroup] = []
    cursor = _Cursor(window)
    pending: list[PlannedTask] = []
    for task in tasks:
        pending.append(task)
        if task.commit_subjects:
            groups.append(cursor.close_group(tuple(pending), task))
            pending = []
    if pending:
        groups.append(TaskGroup(tuple(pending), GroupStatus.UNMARKED, None, None, None))
    return tuple(groups)


class _Cursor:
    """Walks the window's commits, handing each group the commits since the last marker."""

    def __init__(self, window: SliceWindow) -> None:
        self._commits = window.commits
        self._position = {commit.sha: place for place, commit in enumerate(window.commits)}
        self._done = -1  # window position of the last marker found so far

    def close_group(self, tasks: tuple[PlannedTask, ...], marker_task: PlannedTask) -> TaskGroup:
        found = [
            commit
            for subject in marker_task.commit_subjects
            if (commit := self._earliest_with_subject(subject)) is not None
        ]
        if not found:
            return TaskGroup(tasks, GroupStatus.MARKER_NOT_FOUND, None, None, None)
        end = max(found, key=lambda commit: self._position[commit.sha])
        end_place = self._position[end.sha]
        if end_place <= self._done:
            _logger.warning(
                "marker %s for task %d precedes an earlier marker; its group has no commits",
                end.sha,
                marker_task.number,
            )
            return TaskGroup(tasks, GroupStatus.ATTRIBUTED, end, 0, timedelta(0))
        start = self._commits[self._done] if self._done >= 0 else self._commits[0]
        in_group = self._commits[self._done + 1 : end_place + 1]
        marker_shas = {commit.sha for commit in found}
        extra = sum(1 for commit in in_group if commit.sha not in marker_shas)
        self._done = end_place
        return TaskGroup(tasks, GroupStatus.ATTRIBUTED, end, extra, end.authored_at - start.authored_at)

    def _earliest_with_subject(self, subject: str) -> Commit | None:
        return next((commit for commit in self._commits if commit.subject == subject), None)
