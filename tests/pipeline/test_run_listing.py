"""Run listing: resume points and problems for each run (slice 199)."""

from __future__ import annotations

import dataclasses
import logging
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
    RunSummary,
    list_run_summaries,
)
from squadron.pipeline.state import StateManager
from tests.pipeline.run_listing_support import (
    EACH_STEP,
    SECOND_EACH_STEP,
    STEP_NAMES,
    Counting,
    begin,
    complete_steps,
    completed_batch_run,
    definition_loader,
    end,
    fail_at,
    mixed_records,
    pause_at,
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
    return list_run_summaries(
        sm,
        pipeline=pipeline,
        include_all=include_all,
        load_definition=load_definition or definition_loader(pipelines),
        load_report=load_report or BatchReport.load,
    )


def _only(summaries: list[RunSummary]) -> RunSummary:
    assert len(summaries) == 1, summaries
    return summaries[0]


def _warned(caplog: pytest.LogCaptureFixture, *fragments: str) -> bool:
    return any(
        r.name == _LOGGER
        and r.levelno == logging.WARNING
        and all(f in r.getMessage() for f in fragments)
        for r in caplog.records
    )


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

        with caplog.at_level(logging.WARNING, logger=_LOGGER):
            summaries = _list(sm, pipelines, load_definition=loader)

        assert loader.calls == ["gone"]
        assert [s.problem for s in summaries] == [ResumeProblem.PIPELINE_UNAVAILABLE] * 2
        assert all(s.resume is None for s in summaries)
        assert _warned(caplog, summaries[0].run_id, "gone", "unavailable")

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
        assert _warned(caplog, run_id, "no unfinished step")


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

    def test_running_run_has_nothing_to_resume(self, sm: StateManager, pipelines: Path) -> None:
        begin(sm, "steps")

        assert _list(sm, pipelines) == []
        summary = _only(_list(sm, pipelines, include_all=True))
        assert (summary.resume, summary.problem) == (None, None)

    def test_pipeline_with_two_each_steps_is_unsupported(
        self, sm: StateManager, pipelines: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        run_id = completed_batch_run(sm, "batch")
        write_batch_pipeline(pipelines, "batch", (EACH_STEP, SECOND_EACH_STEP))  # edited later

        with caplog.at_level(logging.WARNING, logger=_LOGGER):
            summary = _only(_list(sm, pipelines))

        assert summary.problem is ResumeProblem.ITEM_RESUME_UNSUPPORTED
        assert _warned(caplog, run_id, "has 2 each steps")

    def test_corrupt_report_is_unreadable(
        self, sm: StateManager, pipelines: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        run_id = completed_batch_run(sm, "batch")
        path = report_json_path(sm.runs_dir, run_id, EACH_STEP)
        path.write_text("{not json")

        with caplog.at_level(logging.WARNING, logger=_LOGGER):
            summary = _only(_list(sm, pipelines))

        assert summary.problem is ResumeProblem.REPORT_UNREADABLE
        assert _warned(caplog, run_id, str(path))

    def test_renamed_each_step_is_unreadable(
        self, sm: StateManager, pipelines: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        run_id = completed_batch_run(sm, "batch")
        write_batch_pipeline(pipelines, "batch", ("renamed",))
        expected = report_json_path(sm.runs_dir, run_id, "renamed")

        with caplog.at_level(logging.WARNING, logger=_LOGGER):
            summary = _only(_list(sm, pipelines))

        assert summary.problem is ResumeProblem.REPORT_UNREADABLE
        assert _warned(caplog, run_id, str(expected))

    def test_completed_batch_run_of_a_deleted_pipeline(
        self, sm: StateManager, pipelines: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        run_id = completed_batch_run(sm, "batch")
        (pipelines / "batch.yaml").unlink()

        with caplog.at_level(logging.WARNING, logger=_LOGGER):
            summary = _only(_list(sm, pipelines))

        assert summary.problem is ResumeProblem.PIPELINE_UNAVAILABLE
        assert _warned(caplog, run_id, "batch", "unavailable")


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

    def test_default_view_hides_nothing_to_resume_and_keeps_problems(
        self, sm: StateManager, pipelines: Path
    ) -> None:
        paused = begin(sm, "steps")
        pause_at(sm, paused, STEP_NAMES[0])
        broken = begin(sm, "gone")
        pause_at(sm, broken, "design-0")
        begin(sm, "steps")  # running
        completed_batch_run(sm, "batch", [BatchItemRecord("1", "a", ItemOutcome.PASSED)])

        shown = {s.run_id for s in _list(sm, pipelines)}

        assert shown == {paused, broken}

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

    summaries = _list(
        sm, pipelines, include_all=True, load_definition=load_definition, load_report=load_report
    )

    assert len(summaries) == 300
    assert len(load_definition.calls) == len(set(load_definition.calls)) == 4
    assert len(load_report.calls) == 50


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
