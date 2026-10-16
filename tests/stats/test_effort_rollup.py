"""The effort rollup across completed slices (slice 176 D2, D7, D9)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from squadron.pipeline.state import StateManager
from squadron.review.git_utils import run_git
from squadron.stats.effort_rollup import (
    NO_COMPLETED_SLICES,
    Measure,
    SlicesEffortReport,
    slices_effort_report,
)
from squadron.stats.git_history import GitHistory
from tests.stats.repo_support import CountingRunner, StatsRepo, write_run_file

_PLAN = "project-documents/user/architecture/300-slices.rollup.md"
_DAY = 86400.0


def _date(day: int) -> str:
    """ISO date ``day`` days after 2026-11-01 (after the 941 cutoff)."""
    return (datetime(2026, 11, 1, 10, tzinfo=UTC) + timedelta(days=day)).isoformat()


def _review(verdict: str, round_number: int) -> str:
    """Each round differs in content, as real rounds do (identical blobs are one version)."""
    return f"---\ndocType: review\nverdict: {verdict}\naiModel: m\n---\n\nRound {round_number}\n"


class Project:
    """A temp project whose slices are added one by one on top of a shared plan file."""

    def __init__(self, repo: StatsRepo, efforts: dict[int, int | None]) -> None:
        self.repo = repo
        self.day = 1
        entries = "".join(
            f"{n}. [x] **({index}) Slice {index}** — text. "
            + (f"Effort: {effort}/5\n" if effort is not None else "\n")
            for n, (index, effort) in enumerate(efforts.items(), start=1)
        )
        repo.commit("init", {"README.md": "x\n", _PLAN: entries}, self._next())

    def _next(self) -> str:
        self.day += 1
        return _date(self.day)

    def add(
        self,
        index: int,
        *,
        status: str = "complete",
        created: str = "20261105",
        impl_days: int | None = 2,
        slice_verdicts: tuple[str, ...] = ("PASS",),
    ) -> None:
        repo = self.repo
        repo.checkout("main")
        tasks = f"project-documents/user/tasks/{index}-tasks.s{index}.md"
        repo.commit(
            "docs: tasks", {tasks: f"### Task 1: T\n\n- [ ] Commit: `feat: s{index}`\n"}, self._next()
        )
        if impl_days is not None:
            repo.branch(f"{index}-slice.s{index}")
            repo.commit(f"feat: s{index}", {f"src/s{index}.py": "1\n"}, self._next())
            self.day += impl_days
            repo.commit(f"feat: s{index} more", {f"src/s{index}.py": "2\n"}, _date(self.day))
            repo.checkout("main")
        design = f"project-documents/user/slices/{index}-slice.s{index}.md"
        front = f"status: {status}\ndateCreated: {created}"
        repo.commit("docs: design", {design: f"---\n{front}\n---\n\nBody\n"}, self._next())
        review = f"project-documents/user/reviews/{index}-review.slice.s{index}.md"
        for round_number, verdict in enumerate(slice_verdicts, start=1):
            repo.commit(f"review {verdict}", {review: _review(verdict, round_number)}, self._next())


def _report(
    repo: StatsRepo, runs_dir: Path, since: str | None = None, runner: CountingRunner | None = None
) -> SlicesEffortReport:
    history = GitHistory(repo.root, run=runner or run_git)
    history.load()
    return slices_effort_report(
        since=since,
        project_root=repo.root,
        history=history,
        state_manager=StateManager(runs_dir=runs_dir),
    )


@pytest.fixture
def runs_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "runs"
    directory.mkdir()
    return directory


@pytest.fixture
def project(stats_repo: StatsRepo) -> Project:
    efforts: dict[int, int | None] = {301: 2, 302: 2, 303: 4, 304: None, 305: 2, 306: 2}
    built = Project(stats_repo, efforts)
    built.add(301, impl_days=2, slice_verdicts=("FAIL", "PASS"))
    built.add(302, impl_days=4)
    built.add(303, impl_days=1, slice_verdicts=("CONCERNS",))
    built.add(304, impl_days=None, slice_verdicts=("FAIL", "FAIL", "PASS"))  # no branch
    built.add(305, status="in_progress")
    built.add(306, created="20261001")
    return built


def test_groups_by_planned_effort_with_n_median_and_range(project: Project, runs_dir: Path) -> None:
    report = _report(project.repo, runs_dir)

    assert report.slices == 5  # 301-304 and 306; 305 is not complete
    assert [(row.level, row.n) for row in report.levels] == [(2, 3), (4, 1), (None, 1)]
    level_two = report.levels[0].measures
    design = level_two[Measure.DESIGN_ROUNDS]
    assert (design.n, design.median, design.minimum, design.maximum) == (3, 1.0, 1, 2)
    span = level_two[Measure.SPAN]
    assert (span.n, span.median, span.minimum, span.maximum) == (
        3,
        2 * _DAY,
        2 * _DAY,
        4 * _DAY,
    )  # 301, 302, 306: 2d, 4d, 2d
    assert level_two[Measure.IMPLEMENTATION_COMMITS].median == 2  # two commits per branch
    assert level_two[Measure.TASKS_ROUNDS].n == 0  # no tasks review exists: unknown, not zero


def test_a_slice_with_no_branch_contributes_rounds_but_not_commit_measures(
    project: Project, runs_dir: Path
) -> None:
    unplanned = _report(project.repo, runs_dir).levels[-1]

    assert unplanned.level is None and unplanned.n == 1
    assert unplanned.measures[Measure.DESIGN_ROUNDS].median == 3  # FAIL, FAIL, PASS
    assert unplanned.measures[Measure.SPAN].n == 0
    assert unplanned.measures[Measure.IMPLEMENTATION_COMMITS].n == 0
    assert unplanned.measures[Measure.FIXUPS].n == 0


def test_since_filters_on_the_design_date_created(project: Project, runs_dir: Path) -> None:
    report = _report(project.repo, runs_dir, since="20261101")

    assert report.slices == 4  # slice 306 was created 20261001
    assert sum(row.n for row in report.levels) == 4


def test_recorded_spend_is_a_per_slice_measure(project: Project, runs_dir: Path) -> None:
    write_run_file(runs_dir, "run-301", 301, cost_usd=0.5)

    spend = _report(project.repo, runs_dir).levels[0].measures[Measure.RECORDED_SPEND]

    assert (spend.n, spend.median) == (1, 0.5)  # only slice 301 has a priced record


def test_no_completed_slices_is_an_empty_report_with_its_reason(
    stats_repo: StatsRepo, runs_dir: Path
) -> None:
    Project(stats_repo, {301: 2}).add(301, status="in_progress")

    report = _report(stats_repo, runs_dir)

    assert (report.levels, report.slices, report.empty_reason) == ((), 0, NO_COMPLETED_SLICES)


def test_since_with_nothing_left_names_the_date_in_the_reason(project: Project, runs_dir: Path) -> None:
    report = _report(project.repo, runs_dir, since="20271231")

    assert report.empty_reason == f"{NO_COMPLETED_SLICES} since 20271231"


def test_git_call_count_is_two_plus_the_versions_read_for_the_whole_rollup(
    project: Project, runs_dir: Path
) -> None:
    runner = CountingRunner()

    _report(project.repo, runs_dir, runner=runner)

    # Slice reviews read for the five completed slices: 2 + 1 + 1 + 3 + 1.
    assert len(runner.calls) == 2 + 8


def test_json_has_levels_with_measures(project: Project, runs_dir: Path) -> None:
    data = _report(project.repo, runs_dir).to_json_dict()

    levels = data["levels"]
    assert isinstance(levels, list)
    assert [level["level"] for level in levels] == [2, 4, None]
    assert levels[0]["measures"]["design_rounds"]["median"] == 1.0
    assert levels[0]["n"] == 3
