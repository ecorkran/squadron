"""plan_prune selection and protection (slice 174 D9). Real run files, real PIDs."""

from __future__ import annotations

import os
import socket
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from squadron.pipeline.executor import ExecutionStatus
from squadron.pipeline.run_liveness import assess_liveness
from squadron.pipeline.run_prune import (
    DEFAULT_CATEGORIES,
    PruneCategory,
    PrunePlan,
    PruneUsageError,
    plan_prune,
)
from squadron.pipeline.state import RunState, StateManager
from tests.pipeline.liveness_support import exited_pid
from tests.pipeline.run_listing_support import (
    STEP_NAMES,
    begin,
    begin_owned,
    definition_loader,
    end,
    fail_at,
    pause_at,
    write_step_pipeline,
)


@dataclass(frozen=True)
class Runs:
    failed: str
    completed: str
    paused: str
    paused_gone: str
    completed_gone: str
    orphan: str
    live: str
    stale: str
    unowned: str
    unowned_gone: str
    junk: str


@pytest.fixture
def pipelines(tmp_path: Path) -> Path:
    directory = tmp_path / "pipelines"
    write_step_pipeline(directory, "steps")
    write_step_pipeline(directory, "other")
    return directory


@pytest.fixture
def sm(tmp_path: Path) -> StateManager:
    return StateManager(runs_dir=tmp_path / "runs")


@pytest.fixture
def runs(sm: StateManager) -> Runs:
    failed = begin(sm, "steps")
    completed = begin(sm, "other")
    paused = begin(sm, "steps")
    paused_gone = begin(sm, "gone")
    completed_gone = begin(sm, "gone")
    orphan = begin_owned(sm, "steps", exited_pid())
    live = begin_owned(sm, "steps", os.getpid())
    stale = begin_owned(sm, "steps", os.getpid())
    unowned = begin(sm, "steps")
    unowned_gone = begin(sm, "gone")
    fail_at(sm, failed, STEP_NAMES[0])
    end(sm, completed, ExecutionStatus.COMPLETED)
    pause_at(sm, paused, STEP_NAMES[0])
    pause_at(sm, paused_gone, "design-0")
    end(sm, completed_gone, ExecutionStatus.COMPLETED)
    state = sm.load(stale)
    state.heartbeat_at = datetime(2020, 1, 1, tzinfo=UTC)
    sm._save(state)  # pyright: ignore[reportPrivateUsage]
    (sm.runs_dir / "run-junk.json").write_text("{not json")
    return Runs(
        failed,
        completed,
        paused,
        paused_gone,
        completed_gone,
        orphan,
        live,
        stale,
        unowned,
        unowned_gone,
        "run-junk",
    )


def _assess(state: RunState):  # type: ignore[no-untyped-def]
    return assess_liveness(state, now=datetime.now(UTC), hostname=socket.gethostname())


def _plan(
    sm: StateManager,
    pipelines: Path,
    *,
    statuses: set[PruneCategory] | None = None,
    run_ids: tuple[str, ...] = (),
    pipeline: str | None = None,
    older_than: timedelta | None = None,
    now: datetime | None = None,
) -> PrunePlan:
    return plan_prune(
        sm.scan_runs(),
        runs_dir=sm.runs_dir,
        statuses=None if statuses is None else frozenset(statuses),
        run_ids=run_ids,
        pipeline=pipeline,
        older_than=older_than,
        now=now or datetime.now(UTC),
        load_definition=definition_loader(pipelines),
        assess=_assess,
    )


def _ids(plan: PrunePlan) -> set[str]:
    return {c.run_id for c in plan.candidates}


class TestCategories:
    def test_each_run_carries_its_categories(
        self, sm: StateManager, pipelines: Path, runs: Runs
    ) -> None:
        plan = _plan(sm, pipelines, statuses=set(PruneCategory))
        cats = {c.run_id: c.categories for c in plan.candidates}

        assert cats[runs.failed] == {PruneCategory.FAILED}
        assert cats[runs.completed] == {PruneCategory.COMPLETED}
        assert cats[runs.paused] == {PruneCategory.PAUSED}
        assert cats[runs.paused_gone] == {PruneCategory.PAUSED, PruneCategory.UNAVAILABLE}
        assert cats[runs.completed_gone] == {PruneCategory.COMPLETED, PruneCategory.UNAVAILABLE}
        assert cats[runs.orphan] == {PruneCategory.ORPHANED}
        assert cats[runs.stale] == {PruneCategory.STALE}
        assert cats[runs.unowned] == {PruneCategory.UNOWNED}
        assert cats[runs.unowned_gone] == {PruneCategory.UNOWNED, PruneCategory.UNAVAILABLE}
        assert cats[runs.junk] == {PruneCategory.UNREADABLE}
        assert runs.live not in cats

    @pytest.mark.parametrize("category", list(PruneCategory))
    def test_status_selects_only_that_category(
        self, sm: StateManager, pipelines: Path, runs: Runs, category: PruneCategory
    ) -> None:
        plan = _plan(sm, pipelines, statuses={category})

        assert plan.candidates
        assert all(category in c.categories for c in plan.candidates)


class TestDefaultSelection:
    def test_default_set(self, sm: StateManager, pipelines: Path, runs: Runs) -> None:
        plan = _plan(sm, pipelines)

        assert DEFAULT_CATEGORIES == {
            PruneCategory.FAILED,
            PruneCategory.ORPHANED,
            PruneCategory.UNAVAILABLE,
            PruneCategory.UNREADABLE,
        }
        assert _ids(plan) == {runs.failed, runs.completed_gone, runs.orphan, runs.junk}
        assert plan.refusals == []

    def test_default_protects_paused_unowned_stale_completed_live(
        self, sm: StateManager, pipelines: Path, runs: Runs
    ) -> None:
        excluded = {
            runs.paused,
            runs.paused_gone,  # paused, though it also matches unavailable
            runs.unowned,
            runs.unowned_gone,  # unowned, though it also matches unavailable
            runs.stale,
            runs.completed,
            runs.live,
        }
        assert not _ids(_plan(sm, pipelines)) & excluded


class TestProtection:
    def test_paused_needs_its_status_even_when_unavailable_is_selected(
        self, sm: StateManager, pipelines: Path, runs: Runs
    ) -> None:
        assert runs.paused_gone not in _ids(_plan(sm, pipelines, statuses={PruneCategory.UNAVAILABLE}))
        both = {PruneCategory.UNAVAILABLE, PruneCategory.PAUSED}
        assert runs.paused_gone in _ids(_plan(sm, pipelines, statuses=both))

    def test_unowned_needs_its_status(self, sm: StateManager, pipelines: Path, runs: Runs) -> None:
        assert runs.unowned_gone not in _ids(_plan(sm, pipelines, statuses={PruneCategory.UNAVAILABLE}))
        assert _ids(_plan(sm, pipelines, statuses={PruneCategory.UNOWNED})) == {
            runs.unowned,
            runs.unowned_gone,
        }

    def test_stale_only_by_status_or_name(self, sm: StateManager, pipelines: Path, runs: Runs) -> None:
        assert _ids(_plan(sm, pipelines, statuses={PruneCategory.STALE})) == {runs.stale}
        assert _ids(_plan(sm, pipelines, run_ids=(runs.stale,))) == {runs.stale}

    def test_named_protected_runs_are_selected(
        self, sm: StateManager, pipelines: Path, runs: Runs
    ) -> None:
        plan = _plan(sm, pipelines, run_ids=(runs.paused, runs.unowned, runs.completed))

        assert _ids(plan) == {runs.paused, runs.unowned, runs.completed}

    def test_named_live_run_is_refused(self, sm: StateManager, pipelines: Path, runs: Runs) -> None:
        plan = _plan(sm, pipelines, run_ids=(runs.live, runs.failed))

        assert _ids(plan) == {runs.failed}
        assert [(r.run_id, r.reason) for r in plan.refusals] == [(runs.live, "run is live; not pruned")]

    def test_live_run_is_never_a_candidate(self, sm: StateManager, pipelines: Path, runs: Runs) -> None:
        assert runs.live not in _ids(_plan(sm, pipelines, statuses=set(PruneCategory)))

    def test_unknown_run_id_is_refused(self, sm: StateManager, pipelines: Path, runs: Runs) -> None:
        plan = _plan(sm, pipelines, run_ids=("run-nope",))

        assert plan.candidates == []
        assert [r.run_id for r in plan.refusals] == ["run-nope"]


class TestSelectionAndFilters:
    def test_run_ids_with_status_is_a_usage_error(
        self, sm: StateManager, pipelines: Path, runs: Runs
    ) -> None:
        with pytest.raises(PruneUsageError):
            _plan(sm, pipelines, run_ids=(runs.failed,), statuses={PruneCategory.FAILED})

    def test_pipeline_filter_is_case_insensitive_and_excludes_unreadable(
        self, sm: StateManager, pipelines: Path, runs: Runs
    ) -> None:
        plan = _plan(sm, pipelines, pipeline="STEPS")

        assert _ids(plan) == {runs.failed, runs.orphan}

    def test_older_than(self, sm: StateManager, pipelines: Path, runs: Runs) -> None:
        assert _ids(_plan(sm, pipelines, older_than=timedelta(days=1))) == set()
        later = datetime.now(UTC) + timedelta(days=2)
        aged = _plan(sm, pipelines, older_than=timedelta(days=1), now=later)
        assert _ids(aged) == {runs.failed, runs.completed_gone, runs.orphan, runs.junk}

    def test_pipeline_and_older_than_combine(
        self, sm: StateManager, pipelines: Path, runs: Runs
    ) -> None:
        later = datetime.now(UTC) + timedelta(days=2)

        plan = _plan(sm, pipelines, pipeline="gone", older_than=timedelta(days=1), now=later)

        assert _ids(plan) == {runs.completed_gone}

    def test_unreadable_age_comes_from_mtime(
        self, sm: StateManager, pipelines: Path, runs: Runs
    ) -> None:
        junk = sm.runs_dir / "run-junk.json"
        three_days_ago = (datetime.now(UTC) - timedelta(days=3)).timestamp()
        os.utime(junk, (three_days_ago, three_days_ago))

        plan = _plan(sm, pipelines, statuses={PruneCategory.UNREADABLE}, older_than=timedelta(days=2))

        (candidate,) = plan.candidates
        assert candidate.run_id == runs.junk
        assert candidate.age is not None and candidate.age >= timedelta(days=3)
        assert candidate.pipeline is None
