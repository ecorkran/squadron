"""Run listing: resume points and problems for each run (slice 199)."""

from __future__ import annotations

import dataclasses
import logging
import os
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from squadron.pipeline import item_resume
from squadron.pipeline.batch_report import (
    BatchItemRecord,
    BatchReport,
    ItemDecision,
    ItemOutcome,
    report_json_path,
)
from squadron.pipeline.executor import ExecutionStatus
from squadron.pipeline.item_resume import ResumeRequest
from squadron.pipeline.models import PipelineDefinition
from squadron.pipeline.run_listing import (
    ResumeKind,
    ResumePoint,
    ResumeProblem,
    RunListing,
    RunSummary,
    list_run_summaries,
)
from squadron.pipeline.run_liveness import RunLiveness, process_alive
from squadron.pipeline.state import ActiveItem, StateManager
from tests.pipeline.liveness_support import exited_pid
from tests.pipeline.run_listing_support import (
    EACH_STEP,
    SECOND_EACH_STEP,
    STEP_NAMES,
    Counting,
    begin,
    begin_owned,
    complete_steps,
    completed_batch_run,
    definition_loader,
    end,
    fail_at,
    mixed_records,
    pause_at,
    warned,
    write_batch_pipeline,
    write_step_pipeline,
)

_LOGGER = "squadron.pipeline.run_listing"


@pytest.fixture
def pipelines(tmp_path: Path) -> Path:
    directory = tmp_path / "pipelines"
    write_step_pipeline(directory, "steps")
    write_batch_pipeline(directory, "batch")
    return directory


@pytest.fixture
def sm(tmp_path: Path) -> StateManager:
    return StateManager(runs_dir=tmp_path / "runs")


def _list(
    sm: StateManager,
    pipelines: Path,
    *,
    include_all: bool = False,
    pipeline: str | None = None,
    load_definition: Counting[[str], PipelineDefinition] | None = None,
    load_report: Counting[[Path], BatchReport] | None = None,
) -> list[RunSummary]:
    return _listing(
        sm,
        pipelines,
        include_all=include_all,
        pipeline=pipeline,
        load_definition=load_definition,
        load_report=load_report,
    ).rows


def _listing(
    sm: StateManager,
    pipelines: Path,
    *,
    include_all: bool = False,
    pipeline: str | None = None,
    load_definition: Counting[[str], PipelineDefinition] | None = None,
    load_report: Counting[[Path], BatchReport] | None = None,
    process_alive: Callable[[int], bool | None] = process_alive,
) -> RunListing:
    return list_run_summaries(
        sm,
        pipeline=pipeline,
        include_all=include_all,
        load_definition=load_definition or definition_loader(pipelines),
        load_report=load_report or BatchReport.load,
        process_alive=process_alive,
    )


def _only(summaries: list[RunSummary]) -> RunSummary:
    assert len(summaries) == 1, summaries
    return summaries[0]


# ---------------------------------------------------------------------------
# Row types (D6, D10)
# ---------------------------------------------------------------------------


class TestRowTypes:
    def test_resume_point_is_frozen(self) -> None:
        point = ResumePoint(ResumeKind.STEP, "design")
        with pytest.raises(dataclasses.FrozenInstanceError):
            point.step_name = "other"  # type: ignore[misc]

    def test_run_summary_is_frozen(self) -> None:
        summary = RunSummary("r", "p", {}, "paused", None, None, datetime.now(UTC))
        with pytest.raises(dataclasses.FrozenInstanceError):
            summary.status = "failed"  # type: ignore[misc]

    def test_enum_members(self) -> None:
        assert {m.name for m in ResumeKind} == {"STEP", "ITEMS"}
        assert {m.name for m in ResumeProblem} == {
            "PIPELINE_UNAVAILABLE",
            "NO_UNFINISHED_STEP",
            "ITEM_RESUME_UNSUPPORTED",
            "REPORT_UNREADABLE",
        }


# ---------------------------------------------------------------------------
# Definition loading (D7, D12)
# ---------------------------------------------------------------------------


class TestDefinitionLoading:
    def test_two_runs_of_one_pipeline_load_once(self, sm: StateManager, pipelines: Path) -> None:
        for _ in range(2):
            pause_at(sm, begin(sm, "steps"), STEP_NAMES[0])
        loader = Counting(definition_loader(pipelines))

        _list(sm, pipelines, load_definition=loader)

        assert loader.calls == ["steps"]

    @pytest.mark.parametrize(
        "contents", [None, "steps: [unclosed\n", "name: broken\ndescription: no steps\n"]
    )
    def test_unloadable_pipeline_is_unavailable_and_tried_once(
        self,
        sm: StateManager,
        pipelines: Path,
        caplog: pytest.LogCaptureFixture,
        contents: str | None,
    ) -> None:
        """Missing file, malformed YAML, schema-invalid file."""
        if contents is not None:
            (pipelines / "gone.yaml").write_text(contents)
        for _ in range(2):
            pause_at(sm, begin(sm, "gone"), "design-0")
        loader = Counting(definition_loader(pipelines))

        with caplog.at_level(logging.DEBUG, logger=_LOGGER):
            listing = _listing(sm, pipelines, load_definition=loader)

        assert loader.calls == ["gone"]
        assert [s.problem for s in listing.rows] == [ResumeProblem.PIPELINE_UNAVAILABLE] * 2
        assert all(s.resume is None for s in listing.rows)
        assert list(listing.unavailable) == ["gone"]
        assert listing.unavailable_runs == 2
        # Reported once per pipeline at DEBUG, never per run (174 D10).
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert sum("gone" in r.getMessage() for r in caplog.records) == 1

    def test_other_loader_errors_propagate(self, sm: StateManager, pipelines: Path) -> None:
        pause_at(sm, begin(sm, "steps"), STEP_NAMES[0])

        def explode(name: str) -> PipelineDefinition:
            raise RuntimeError(name)

        with pytest.raises(RuntimeError, match="steps"):
            list_run_summaries(sm, pipeline=None, include_all=False, load_definition=explode)


# ---------------------------------------------------------------------------
# Paused and failed runs
# ---------------------------------------------------------------------------


class TestStepResume:
    def test_paused_run_resumes_at_the_paused_step(self, sm: StateManager, pipelines: Path) -> None:
        run_id = begin(sm, "steps")
        pause_at(sm, run_id, STEP_NAMES[1], done=[STEP_NAMES[0]])
        definition = definition_loader(pipelines)("steps")

        summary = _only(_list(sm, pipelines))

        assert summary.resume == ResumePoint(ResumeKind.STEP, STEP_NAMES[1])
        assert summary.problem is None
        assert STEP_NAMES[1] == sm.first_unfinished_step(run_id, definition)

    def test_failed_run_resumes_at_the_failed_step(self, sm: StateManager, pipelines: Path) -> None:
        run_id = begin(sm, "steps")
        fail_at(sm, run_id, STEP_NAMES[2], done=STEP_NAMES[:2])
        definition = definition_loader(pipelines)("steps")

        summary = _only(_list(sm, pipelines))

        assert summary.status == ExecutionStatus.FAILED.value
        assert summary.resume == ResumePoint(ResumeKind.STEP, STEP_NAMES[2])
        assert STEP_NAMES[2] == sm.first_unfinished_step(run_id, definition)

    def test_paused_run_with_no_unfinished_step(
        self, sm: StateManager, pipelines: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        run_id = begin(sm, "steps")
        complete_steps(sm, run_id, STEP_NAMES)
        end(sm, run_id, ExecutionStatus.PAUSED)

        with caplog.at_level(logging.WARNING, logger=_LOGGER):
            summary = _only(_list(sm, pipelines))

        assert summary.resume is None
        assert summary.problem is ResumeProblem.NO_UNFINISHED_STEP
        assert warned(caplog, _LOGGER, run_id, "no unfinished step")


# ---------------------------------------------------------------------------
# Completed and running runs
# ---------------------------------------------------------------------------


class TestItemResume:
    def test_mixed_flag_kinds_count_open_and_acceptable(
        self, sm: StateManager, pipelines: Path
    ) -> None:
        completed_batch_run(sm, "batch")

        summary = _only(_list(sm, pipelines))

        assert summary.resume == ResumePoint(ResumeKind.ITEMS, EACH_STEP, 3, 1)
        assert summary.problem is None

    def test_all_items_passed_has_nothing_to_resume(self, sm: StateManager, pipelines: Path) -> None:
        completed_batch_run(sm, "batch", [BatchItemRecord("1", "a", ItemOutcome.PASSED)])

        assert _list(sm, pipelines) == []
        assert _only(_list(sm, pipelines, include_all=True)).resume is None

    def test_completed_non_batch_run_loads_no_definition(
        self, sm: StateManager, pipelines: Path
    ) -> None:
        run_id = begin(sm, "steps")
        complete_steps(sm, run_id, STEP_NAMES)
        end(sm, run_id, ExecutionStatus.COMPLETED)
        loader = Counting(definition_loader(pipelines))

        summaries = _list(sm, pipelines, include_all=True, load_definition=loader)

        assert loader.calls == []
        assert (summaries[0].resume, summaries[0].problem) == (None, None)

    def test_running_run_is_shown_with_nothing_to_resume(
        self, sm: StateManager, pipelines: Path
    ) -> None:
        begin(sm, "steps")

        summary = _only(_list(sm, pipelines))
        assert (summary.resume, summary.problem) == (None, None)
        assert summary.liveness is not None
        assert summary.liveness.liveness is RunLiveness.UNOWNED

    def test_pipeline_with_two_each_steps_is_unsupported(
        self, sm: StateManager, pipelines: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        run_id = completed_batch_run(sm, "batch")
        write_batch_pipeline(pipelines, "batch", (EACH_STEP, SECOND_EACH_STEP))  # edited later

        with caplog.at_level(logging.WARNING, logger=_LOGGER):
            summary = _only(_list(sm, pipelines))

        assert summary.problem is ResumeProblem.ITEM_RESUME_UNSUPPORTED
        assert warned(caplog, _LOGGER, run_id, "has 2 each steps")

    def test_corrupt_report_is_unreadable(
        self, sm: StateManager, pipelines: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        run_id = completed_batch_run(sm, "batch")
        path = report_json_path(sm.runs_dir, run_id, EACH_STEP)
        path.write_text("{not json")

        with caplog.at_level(logging.WARNING, logger=_LOGGER):
            summary = _only(_list(sm, pipelines))

        assert summary.problem is ResumeProblem.REPORT_UNREADABLE
        assert warned(caplog, _LOGGER, run_id, str(path))

    def test_renamed_each_step_is_unreadable(
        self, sm: StateManager, pipelines: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        run_id = completed_batch_run(sm, "batch")
        write_batch_pipeline(pipelines, "batch", ("renamed",))
        expected = report_json_path(sm.runs_dir, run_id, "renamed")

        with caplog.at_level(logging.WARNING, logger=_LOGGER):
            summary = _only(_list(sm, pipelines))

        assert summary.problem is ResumeProblem.REPORT_UNREADABLE
        assert warned(caplog, _LOGGER, run_id, str(expected))

    def test_completed_batch_run_of_a_deleted_pipeline(
        self, sm: StateManager, pipelines: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        run_id = completed_batch_run(sm, "batch")
        (pipelines / "batch.yaml").unlink()

        listing = _listing(sm, pipelines)

        summary = _only(listing.rows)
        assert summary.run_id == run_id
        assert summary.problem is ResumeProblem.PIPELINE_UNAVAILABLE
        assert set(listing.unavailable) == {"batch"}


# ---------------------------------------------------------------------------
# list_run_summaries: filters, order, inclusion
# ---------------------------------------------------------------------------


class TestListRunSummaries:
    def test_pipeline_filter_is_case_insensitive(self, sm: StateManager, pipelines: Path) -> None:
        pause_at(sm, begin(sm, "steps"), STEP_NAMES[0])
        completed_batch_run(sm, "batch")

        summaries = _list(sm, pipelines, pipeline="BATCH")

        assert [s.pipeline for s in summaries] == ["batch"]

    def test_newest_first(self, sm: StateManager, pipelines: Path) -> None:
        older = begin(sm, "steps")
        pause_at(sm, older, STEP_NAMES[0])
        newer = completed_batch_run(sm, "batch")

        assert [s.run_id for s in _list(sm, pipelines)] == [newer, older]

    def test_default_view_hides_nothing_to_resume_and_keeps_problems_and_running(
        self, sm: StateManager, pipelines: Path
    ) -> None:
        paused = begin(sm, "steps")
        pause_at(sm, paused, STEP_NAMES[0])
        broken = begin(sm, "gone")
        pause_at(sm, broken, "design-0")
        running = begin(sm, "steps")
        completed_batch_run(sm, "batch", [BatchItemRecord("1", "a", ItemOutcome.PASSED)])

        shown = {s.run_id for s in _list(sm, pipelines)}

        assert shown == {paused, broken, running}

    def test_include_all_returns_every_run(self, sm: StateManager, pipelines: Path) -> None:
        pause_at(sm, begin(sm, "steps"), STEP_NAMES[0])
        begin(sm, "steps")
        completed_batch_run(sm, "batch", [BatchItemRecord("1", "a", ItemOutcome.PASSED)])

        summaries = _list(sm, pipelines, include_all=True)

        assert len(summaries) == 3
        assert sum(1 for s in summaries if s.resume is None and s.problem is None) == 2


# ---------------------------------------------------------------------------
# I/O bounds and listing/resume parity (D12, D3)
# ---------------------------------------------------------------------------


def test_io_is_bounded_per_pipeline_and_per_batch_run(sm: StateManager, pipelines: Path) -> None:
    for name in ("steps-a", "steps-b"):
        write_step_pipeline(pipelines, name)
    for name in ("batch-a", "batch-b"):
        write_batch_pipeline(pipelines, name)
    # init_run prunes terminal runs, so every run starts before any finishes.
    plain = [begin(sm, f"plain-{i % 20}") for i in range(200)]
    batch = [begin(sm, f"batch-{'ab'[i % 2]}", {"plan": "180"}) for i in range(50)]
    paused = [begin(sm, "steps-a") for _ in range(30)]
    failed = [begin(sm, "steps-b") for _ in range(20)]
    live_pid, dead_pid = os.getpid(), exited_pid()
    for i in range(20):
        begin_owned(sm, f"steps-{'ab'[i % 2]}", live_pid if i < 10 else dead_pid)
    for run_id in plain:
        end(sm, run_id, ExecutionStatus.COMPLETED)
    for i, run_id in enumerate(batch):
        BatchReport(f"batch-{'ab'[i % 2]}", run_id, EACH_STEP, records=mixed_records()).write(
            sm.runs_dir
        )
        end(sm, run_id, ExecutionStatus.COMPLETED)
    for run_id in paused:
        pause_at(sm, run_id, STEP_NAMES[0])
    for run_id in failed:
        fail_at(sm, run_id, STEP_NAMES[0])
    load_definition = Counting(definition_loader(pipelines))
    load_report = Counting(BatchReport.load)
    checks = Counting(process_alive)

    listing = _listing(
        sm,
        pipelines,
        include_all=True,
        load_definition=load_definition,
        load_report=load_report,
        process_alive=checks,
    )

    assert len(listing.rows) == 320
    assert len(load_definition.calls) == len(set(load_definition.calls)) == 4
    assert len(load_report.calls) == 50
    assert len(checks.calls) == 20


def test_listing_counts_match_what_item_resume_accepts(sm: StateManager, pipelines: Path) -> None:
    run_id = completed_batch_run(sm, "batch")
    summary = _only(_list(sm, pipelines))
    path = report_json_path(sm.runs_dir, run_id, EACH_STEP)
    report = BatchReport.load(path)

    def passes(index: str, decision: ItemDecision) -> bool:
        request = ResumeRequest(run_id=run_id, index=index, decision=decision)
        try:
            item_resume._check_record(report, request, path)  # pyright: ignore[reportPrivateUsage]
        except item_resume._Stop:  # pyright: ignore[reportPrivateUsage]
            return False
        return True

    assert summary.resume is not None
    indexes = [r.index for r in report.records]
    assert summary.resume.open_items == sum(passes(i, ItemDecision.RETRY) for i in indexes)
    assert summary.resume.acceptable_items == sum(passes(i, ItemDecision.ACCEPT) for i in indexes)


# ---------------------------------------------------------------------------
# Liveness rows (slice 174 D3)
# ---------------------------------------------------------------------------


class TestLivenessRows:
    def test_each_liveness_state_is_a_row(self, sm: StateManager, pipelines: Path) -> None:
        live = begin_owned(sm, "steps", os.getpid())
        orphan = begin_owned(sm, "steps", exited_pid())
        unowned = begin(sm, "steps")
        stale = begin_owned(sm, "steps", os.getpid())
        state = sm.load(stale)
        state.heartbeat_at = datetime(2020, 1, 1, tzinfo=UTC)
        sm._save(state)  # pyright: ignore[reportPrivateUsage]

        rows = {row.run_id: row for row in _list(sm, pipelines)}

        def liveness(run_id: str) -> RunLiveness | None:
            assessment = rows[run_id].liveness
            return None if assessment is None else assessment.liveness

        assert liveness(live) is RunLiveness.LIVE
        assert liveness(orphan) is RunLiveness.ORPHANED
        assert liveness(unowned) is RunLiveness.UNOWNED
        assert liveness(stale) is RunLiveness.STALE

    def test_running_row_carries_active_step_and_item(self, sm: StateManager, pipelines: Path) -> None:
        run_id = begin_owned(sm, "batch", os.getpid(), {"plan": "180"})
        sm.record_step_started(run_id, EACH_STEP)
        item = ActiveItem(position=2, total=12, index="182")
        sm.record_item_started(run_id, item)

        row = _only(_list(sm, pipelines))

        assert row.active_step == EACH_STEP
        assert row.active_item == item

    def test_running_rows_load_no_definition_or_report(self, sm: StateManager, pipelines: Path) -> None:
        begin_owned(sm, "gone", exited_pid())
        loader = Counting(definition_loader(pipelines))

        listing = _listing(sm, pipelines, load_definition=loader)

        assert loader.calls == []
        assert listing.unavailable == {}

    def test_unavailable_has_one_entry_per_pipeline(
        self, sm: StateManager, pipelines: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        for name in ("gone-a", "gone-a", "gone-b"):
            pause_at(sm, begin(sm, name), "design-0")

        with caplog.at_level(logging.WARNING, logger=_LOGGER):
            listing = _listing(sm, pipelines)

        assert set(listing.unavailable) == {"gone-a", "gone-b"}
        assert listing.unavailable_runs == 3
        assert not caplog.records
