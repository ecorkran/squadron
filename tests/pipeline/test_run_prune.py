"""plan_prune selection and protection (slice 174 D9). Real run files, real PIDs."""

from __future__ import annotations

import dataclasses
import logging
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
    PruneCandidate,
    PruneCategory,
    PrunePlan,
    PruneResult,
    PruneUsageError,
    apply_prune,
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
    newer_schema: str


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
    (sm.runs_dir / "run-newer.json").write_text('{"schema_version": 99, "run_id": "run-newer"}')
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
        "run-newer",
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
        assert cats[runs.newer_schema] == {PruneCategory.UNSUPPORTED_SCHEMA}
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
            runs.newer_schema,  # a newer squadron's file is not junk
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


# ---------------------------------------------------------------------------
# apply_prune
# ---------------------------------------------------------------------------


def _write_run_with_reports(runs_dir: Path, run_id: str) -> list[Path]:
    runs_dir.mkdir(parents=True, exist_ok=True)
    paths = [
        runs_dir / f"{run_id}.json",
        runs_dir / f"{run_id}.slices.report.json",
        runs_dir / f"{run_id}.slices.report.md",
    ]
    for path in paths:
        path.write_text("x")
    return paths


def _plan_for(runs_dir: Path, *run_ids: str) -> PrunePlan:
    candidates = [
        PruneCandidate(
            run_id=run_id,
            pipeline="p",
            status="failed",
            categories=frozenset({PruneCategory.FAILED}),
            age=timedelta(days=1),
            path=runs_dir / f"{run_id}.json",
        )
        for run_id in run_ids
    ]
    return PrunePlan(candidates, [])


class TestApplyPrune:
    def test_removes_state_and_reports_and_keeps_other_runs(self, tmp_path: Path) -> None:
        gone = _write_run_with_reports(tmp_path, "run-a")
        kept = _write_run_with_reports(tmp_path, "run-ab")

        result = apply_prune(_plan_for(tmp_path, "run-a"), tmp_path)

        assert result == PruneResult(removed=1, failed=0)
        assert not any(p.exists() for p in gone)
        assert all(p.exists() for p in kept)

    def test_missing_file_is_not_a_failure(self, tmp_path: Path) -> None:
        result = apply_prune(_plan_for(tmp_path, "run-never-there"), tmp_path)

        assert result == PruneResult(removed=1, failed=0)

    def test_undeletable_file_logs_error_and_continues(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        stuck = _write_run_with_reports(tmp_path, "run-stuck")
        # A directory where the state file should be: unlink() raises an OSError.
        stuck[0].unlink()
        stuck[0].mkdir()
        (stuck[0] / "inside").write_text("x")
        free = _write_run_with_reports(tmp_path, "run-free")

        with caplog.at_level(logging.ERROR, logger="squadron.pipeline.run_prune"):
            result = apply_prune(_plan_for(tmp_path, "run-stuck", "run-free"), tmp_path)

        assert result == PruneResult(removed=1, failed=1)
        assert stuck[0].exists()
        assert not any(p.exists() for p in stuck[1:])  # its reports were still attempted
        assert not any(p.exists() for p in free)
        errors = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(errors) == 1 and str(stuck[0]) in errors[0].getMessage()

    def test_never_deletes_outside_the_runs_dir(self, tmp_path: Path) -> None:
        outside = tmp_path / "elsewhere" / "run-x.json"
        outside.parent.mkdir()
        outside.write_text("x")
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        plan = PrunePlan(
            [dataclasses.replace(_plan_for(runs_dir, "run-x").candidates[0], path=outside)], []
        )

        result = apply_prune(plan, runs_dir)

        assert result.failed == 1
        assert outside.exists()
