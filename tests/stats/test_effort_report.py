"""The single-slice effort report against a real temporary project (slice 176 D7, D9)."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import pytest

from squadron.pipeline.state import StateManager
from squadron.review.git_utils import run_git
from squadron.stats.effort_report import SliceEffortReport, slice_effort_report
from squadron.stats.git_history import GitHistory, WindowSource
from squadron.stats.planning_docs import UnknownSliceError
from squadron.stats.task_attribution import GroupStatus
from tests.stats.repo_support import CountingRunner, StatsRepo, write_run_file

_ARCH = "project-documents/user/architecture/140-slices.x.md"
_TASKS = "project-documents/user/tasks/176-tasks.x.md"
_SLICE_REVIEW = "project-documents/user/reviews/176-review.slice.x.md"
_CODE_REVIEW = "project-documents/user/reviews/176-review.code.x.md"

_PLAN = "1. [ ] **(176) Effort Example** — Does a thing. Dependencies: []. Risk: Low. Effort: 3/5\n"
_TASK_FILE = """## Tasks

### Task 1: First

**Effort**: 2

- [x] done
- [ ] Commit: `feat: one`

### Task 2: Second

- [x] done

Commit: `feat: two`

### Task 3: Never committed

- [ ] Commit: `docs: never made`
"""


def _date(day: int) -> str:
    return f"2026-11-{day:02d}T10:00:00+00:00"  # after the 941 cutoff, so not a lower bound


def _review(verdict: str, cost: str = "") -> str:
    return f"---\ndocType: review\nverdict: {verdict}\naiModel: m\n{cost}---\n\n{verdict}\n"


def _build_project(repo: StatsRepo, *, branch: bool = True, tasks: bool = True) -> None:
    repo.commit("init", {"README.md": "x\n"}, _date(1))
    plan_files = {_ARCH: _PLAN}
    if tasks:
        plan_files[_TASKS] = _TASK_FILE
    repo.commit("docs: plan", plan_files, _date(2))
    repo.commit("review: slice 1", {_SLICE_REVIEW: _review("FAIL")}, _date(2))
    if branch:
        repo.branch("176-slice.x")
    repo.commit("feat: one", {"src/one.py": "1\n"}, _date(3))
    repo.commit("wip", {"src/one.py": "1b\n"}, _date(4))
    repo.commit("feat: two", {"src/two.py": "2\n"}, _date(5))
    cost = "promptTokens: 100\ncostUsd: 0.25\ncostBasis: provider\n"
    repo.commit("review: slice 2", {_SLICE_REVIEW: _review("PASS", cost)}, _date(6))
    repo.commit("review: code", {_CODE_REVIEW: _review("PASS")}, _date(7))
    repo.commit("fix: after review", {"src/two.py": "2b\n"}, _date(8))


@pytest.fixture
def runs_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "runs"
    directory.mkdir()
    write_run_file(directory, "run-this-slice", 176)
    write_run_file(directory, "run-other-slice", 999)
    (directory / "run-corrupt.json").write_text("{not json")
    return directory


def _report(
    repo: StatsRepo, runs_dir: Path, index: int = 176, runner: CountingRunner | None = None
) -> SliceEffortReport:
    history = GitHistory(repo.root, run=runner or run_git)
    history.load()
    return slice_effort_report(
        index, project_root=repo.root, history=history, state_manager=StateManager(runs_dir=runs_dir)
    )


def test_header_groups_and_spend_match_the_inputs(stats_repo: StatsRepo, runs_dir: Path) -> None:
    _build_project(stats_repo)

    report = _report(stats_repo, runs_dir)

    assert (report.index, report.title, report.planned_effort) == (176, "Effort Example", 3)
    assert report.window_source is WindowSource.BRANCH
    assert report.span == timedelta(days=6)  # window starts at day 2's review commit, ends day 8
    assert (report.implementation_commits, report.fixups) == (4, 1)
    assert [(r.review_type, r.rounds, r.to_accept) for r in report.reviews] == [
        ("slice", 2, 2),
        ("tasks", 0, None),
        ("code", 1, 1),
    ]
    first, second, third = report.groups
    assert (first.first_task, first.last_task, first.planned_effort) == (1, 1, 2)
    assert (first.status, first.extra, first.checked, first.total) == (GroupStatus.ATTRIBUTED, 0, 1, 2)
    assert (second.status, second.extra, second.planned_effort) == (GroupStatus.ATTRIBUTED, 1, None)
    assert third.status is GroupStatus.MARKER_NOT_FOUND
    assert report.markers_not_found == 1
    assert (report.rounds_skipped, report.lower_bound, report.unreadable_runs) == (0, False, 1)
    # One dispatch in this slice's run ($0.50) and the priced slice review ($0.25); the
    # code review has no cost; the other slice's run and the corrupt file are not counted.
    assert report.spend.run_count == 1
    assert report.spend.llm_actions == 3
    assert (report.spend.totals.cost_usd, report.spend.totals.priced) == (0.75, 2)


def test_missing_task_file_has_no_groups_but_keeps_everything_else(
    stats_repo: StatsRepo, runs_dir: Path
) -> None:
    _build_project(stats_repo, tasks=False)

    report = _report(stats_repo, runs_dir)

    assert report.task_file_missing and report.groups == ()
    assert report.window_source is WindowSource.NONE  # nothing to bound the window by
    assert report.planned_effort == 3 and report.spend.run_count == 1


def test_missing_branch_is_unavailable_but_effort_rounds_and_spend_remain(
    stats_repo: StatsRepo, runs_dir: Path
) -> None:
    _build_project(stats_repo, branch=False)

    report = _report(stats_repo, runs_dir)

    assert report.window_source is WindowSource.NONE
    assert (report.span, report.implementation_commits, report.fixups) == (None, None, None)
    assert [g.status for g in report.groups] == [GroupStatus.UNAVAILABLE]
    assert report.planned_effort == 3
    assert [r.rounds for r in report.reviews] == [2, 0, 1]
    assert report.spend.totals.cost_usd == 0.75


def test_unknown_index_raises_with_the_plan_files_searched(
    stats_repo: StatsRepo, runs_dir: Path
) -> None:
    _build_project(stats_repo)

    with pytest.raises(UnknownSliceError) as raised:
        _report(stats_repo, runs_dir, index=4242)

    assert [p.name for p in raised.value.searched] == ["140-slices.x.md"]


def test_git_call_count_is_two_plus_the_versions_read(stats_repo: StatsRepo, runs_dir: Path) -> None:
    _build_project(stats_repo)
    runner = CountingRunner()

    _report(stats_repo, runs_dir, runner=runner)

    assert len(runner.calls) == 2 + 3  # two slice versions and one code version


def test_json_values_equal_the_dataclass_values(stats_repo: StatsRepo, runs_dir: Path) -> None:
    _build_project(stats_repo)
    report = _report(stats_repo, runs_dir)

    data = report.to_json_dict()

    assert data["index"] == 176 and data["planned_effort"] == 3
    assert data["window_source"] == "branch"
    assert report.span is not None and data["span"] == report.span.total_seconds()
    groups = data["groups"]
    assert isinstance(groups, list) and groups[0]["status"] == "attributed"
    assert groups[2]["status"] == "marker not found"
    spend = data["spend"]
    assert isinstance(spend, dict) and spend["totals"]["cost_usd"] == 0.75
    json.dumps(data)  # fully serializable
