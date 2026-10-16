"""Slice window and task attribution (slice 176 D5, D9)."""

from __future__ import annotations

import logging
from datetime import timedelta
from pathlib import Path

import pytest

from squadron.stats.git_history import GitHistory, WindowSource
from squadron.stats.planning_docs import PlannedTask
from squadron.stats.task_attribution import (
    GroupStatus,
    attribute,
    implementation_commits,
    post_review_fixups,
    slice_window,
)
from tests.stats.repo_support import CountingRunner, StatsRepo

_TASKS = "project-documents/user/tasks/176-tasks.x.md"
_REVIEW = "project-documents/user/reviews/176-review.code.x.md"
_TASK_PATHS = [Path("176-tasks.x.md")]


def _date(day: int) -> str:
    return f"2026-10-{day:02d}T10:00:00+00:00"


def _task(number: int, *subjects: str) -> PlannedTask:
    return PlannedTask(number, f"Task {number}", None, 0, 1, subjects)


@pytest.fixture
def slice_repo(stats_repo: StatsRepo) -> StatsRepo:
    """init and the task file on main, then a branch with code, a rework, and a doc commit."""
    stats_repo.commit("init", {"README.md": "x\n"}, _date(1))
    stats_repo.commit("docs: add tasks", {_TASKS: "# tasks\n"}, _date(2))
    stats_repo.branch("176-slice.x")
    stats_repo.commit("feat: a", {"src/a.py": "a\n"}, _date(3))
    stats_repo.commit("wip", {"src/a.py": "a2\n"}, _date(4))
    stats_repo.commit("test: a", {"tests/test_a.py": "t\n"}, _date(5))
    stats_repo.commit("feat: b done differently", {"src/b.py": "b\n"}, _date(6))
    stats_repo.commit("docs: notes", {"project-documents/user/notes.md": "n\n"}, _date(7))
    return stats_repo


def _loaded(repo: StatsRepo) -> GitHistory:
    history = GitHistory(repo.root)
    history.load()
    return history


def test_branch_window_excludes_the_task_file_commit_and_everything_before(
    slice_repo: StatsRepo,
) -> None:
    window = slice_window(_loaded(slice_repo), 176, _TASK_PATHS)

    assert window.source is WindowSource.BRANCH
    assert [c.subject for c in window.commits] == [
        "feat: a",
        "wip",
        "test: a",
        "feat: b done differently",
        "docs: notes",
    ]


def test_no_branch_means_no_window(stats_repo: StatsRepo) -> None:
    stats_repo.commit("init", {"README.md": "x\n"}, _date(1))
    stats_repo.commit("docs: add tasks", {_TASKS: "# tasks\n"}, _date(2))

    window = slice_window(_loaded(stats_repo), 176, _TASK_PATHS)

    assert (window.source, window.commits) == (WindowSource.NONE, ())


def test_a_task_file_commit_off_the_branch_chain_gives_no_window_and_a_warning(
    stats_repo: StatsRepo, caplog: pytest.LogCaptureFixture
) -> None:
    stats_repo.commit("init", {"README.md": "x\n"}, _date(1))
    stats_repo.branch("176-slice.x")
    stats_repo.commit("feat: a", {"src/a.py": "a\n"}, _date(2))
    stats_repo.checkout("main")
    stats_repo.commit("docs: add tasks", {_TASKS: "# tasks\n"}, _date(3))

    with caplog.at_level(logging.WARNING, logger="squadron.stats.task_attribution"):
        window = slice_window(_loaded(stats_repo), 176, _TASK_PATHS)

    assert window.source is WindowSource.NONE
    assert any("first-parent chain" in r.getMessage() for r in caplog.records)


def test_one_reworded_subject_is_marker_not_found_and_the_others_get_groups(
    slice_repo: StatsRepo,
) -> None:
    window = slice_window(_loaded(slice_repo), 176, _TASK_PATHS)
    tasks = [_task(1, "feat: a"), _task(2, "test: a"), _task(3, "feat: b")]

    first, second, third = attribute(window, tasks)

    assert (first.status, first.marker.subject if first.marker else None) == (
        GroupStatus.ATTRIBUTED,
        "feat: a",
    )
    assert first.extra == 0
    assert (second.status, second.extra) == (GroupStatus.ATTRIBUTED, 1)  # the "wip" commit
    assert second.span == timedelta(days=2)  # feat: a (day 3) to test: a (day 5)
    assert (third.status, third.marker, third.extra) == (GroupStatus.MARKER_NOT_FOUND, None, None)


def test_document_only_commits_inside_a_group_are_not_extras(stats_repo: StatsRepo) -> None:
    stats_repo.commit("init", {"README.md": "x\n"}, _date(1))
    stats_repo.commit("docs: add tasks", {_TASKS: "# tasks\n"}, _date(2))
    stats_repo.commit("docs: review", {"project-documents/user/r.md": "r\n"}, _date(3))
    stats_repo.branch("176-slice.x")
    stats_repo.commit("feat: a", {"src/a.py": "a\n"}, _date(4))
    window = slice_window(_loaded(stats_repo), 176, _TASK_PATHS)

    (group,) = attribute(window, [_task(1, "feat: a")])

    assert [c.subject for c in window.commits] == ["docs: review", "feat: a"]
    assert group.extra == 0


def test_a_duplicate_subject_takes_the_earliest_commit(slice_repo: StatsRepo) -> None:
    slice_repo.commit("feat: a", {"src/a.py": "a3\n"}, _date(8))  # same subject again, later
    window = slice_window(_loaded(slice_repo), 176, _TASK_PATHS)

    (group,) = attribute(window, [_task(1, "feat: a")])

    assert group.marker is not None and group.marker.authored_at.day == 3


def test_a_task_with_several_subjects_ends_at_the_latest_one_found(slice_repo: StatsRepo) -> None:
    window = slice_window(_loaded(slice_repo), 176, _TASK_PATHS)

    (group,) = attribute(window, [_task(1, "feat: a", "test: a", "never committed")])

    assert group.status is GroupStatus.ATTRIBUTED
    assert group.marker is not None and group.marker.subject == "test: a"
    assert group.extra == 1  # "wip"; both found subjects are markers, not extras


def test_no_prescribed_subject_anywhere_leaves_the_groups_unavailable(
    slice_repo: StatsRepo,
) -> None:
    window = slice_window(_loaded(slice_repo), 176, _TASK_PATHS)
    tasks = [_task(1), _task(2)]

    (group,) = attribute(window, tasks)

    assert window.source is WindowSource.BRANCH
    assert group.status is GroupStatus.UNAVAILABLE
    assert group.tasks == tuple(tasks)
    assert (group.marker, group.extra, group.span) == (None, None, None)


def test_a_missing_window_leaves_the_groups_unavailable(stats_repo: StatsRepo) -> None:
    stats_repo.commit("init", {"README.md": "x\n"}, _date(1))
    window = slice_window(_loaded(stats_repo), 176, _TASK_PATHS)

    (group,) = attribute(window, [_task(1, "feat: a")])

    assert group.status is GroupStatus.UNAVAILABLE


def test_trailing_tasks_without_a_subject_form_an_unmarked_group(slice_repo: StatsRepo) -> None:
    window = slice_window(_loaded(slice_repo), 176, _TASK_PATHS)

    marked, trailing = attribute(window, [_task(1, "feat: a"), _task(2)])

    assert marked.status is GroupStatus.ATTRIBUTED
    assert (trailing.status, trailing.marker) == (GroupStatus.UNMARKED, None)


def test_attribution_makes_no_git_calls_beyond_load(slice_repo: StatsRepo) -> None:
    runner = CountingRunner()
    history = GitHistory(slice_repo.root, run=runner)
    history.load()
    calls_after_load = len(runner.calls)

    window = slice_window(history, 176, _TASK_PATHS)
    attribute(window, [_task(1, "feat: a")])
    implementation_commits(window)
    post_review_fixups(history, 176, window)

    assert len(runner.calls) == calls_after_load == 2


def test_document_only_commits_are_not_implementation_commits(slice_repo: StatsRepo) -> None:
    window = slice_window(_loaded(slice_repo), 176, _TASK_PATHS)

    assert [c.subject for c in implementation_commits(window)] == [
        "feat: a",
        "wip",
        "test: a",
        "feat: b done differently",
    ]


def test_only_a_code_commit_after_the_code_review_is_a_fixup(slice_repo: StatsRepo) -> None:
    slice_repo.commit("review: code", {_REVIEW: "# review\n"}, _date(9))
    slice_repo.commit("docs: after review", {"project-documents/user/more.md": "m\n"}, _date(10))
    slice_repo.commit("fix: after review", {"src/a.py": "a4\n"}, _date(11))
    history = _loaded(slice_repo)
    window = slice_window(history, 176, _TASK_PATHS)

    fixups = post_review_fixups(history, 176, window)

    assert [c.subject for c in fixups] == ["fix: after review"]


def test_no_code_review_artifact_means_no_fixups(slice_repo: StatsRepo) -> None:
    history = _loaded(slice_repo)
    window = slice_window(history, 176, _TASK_PATHS)

    assert post_review_fixups(history, 176, window) == ()
