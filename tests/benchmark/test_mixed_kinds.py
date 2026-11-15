"""A case set of one fix case and one slice case, end to end with doubles (slice 426, Task 39).

Each case is routed to its kind's runner, judged (the fix case is not) and reported with each
kind in its own tables, and 422's yield output shows both kinds' rows for the project. Grade
records come from the report fixture's helpers: grading itself runs in
``test_slice_pipeline_end_to_end.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from squadron.benchmark import case_runners
from squadron.benchmark.bench_plan import BenchConfig, Caps
from squadron.benchmark.bench_report_render import render_json, render_text
from squadron.benchmark.case_runners import ReplaySandbox, case_runner_for, register_case_runner
from squadron.benchmark.diff_judge_plan import plan_judge
from squadron.benchmark.diff_judge_runner import JudgeStatus, run_judging
from squadron.benchmark.yield_report import (
    build_yield,
)
from squadron.benchmark.yield_report import (
    render_json as yield_json,
)
from squadron.benchmark.yield_report import (
    render_text as yield_text,
)
from squadron.core.process_runner import ProcessResult, SubprocessRunner
from squadron.metrology.benchmark_models import BenchmarkCase, CaseKind, QualificationOutcome
from squadron.metrology.benchmark_store import BenchmarkRecordStore
from squadron.metrology.slice_case_models import SliceCandidateRejection
from squadron.metrology.slice_case_store import SliceCaseRecordStore
from squadron.metrology.store import MetrologyStore
from tests.benchmark.diff_judge_run_support import JUDGE, NOW, MemorySidecars, ScriptedDispatcher
from tests.benchmark.diff_judge_support import diff_text
from tests.benchmark.pairwise_support import OPUS, SOL, as_slice
from tests.benchmark.report_support import make_world
from tests.benchmark.slice_case_support import PROJECT, qualification
from tests.benchmark.slice_runner_support import CAPS, CONFIG, SandboxDouble, make_tools_dir
from tests.benchmark.test_yield_report import record as fix_record


class _Runner:
    """A case-kind runner double that records which cases it was given."""

    def __init__(self, pipeline: str) -> None:
        self.pipeline = pipeline
        self.producer_step = pipeline
        self.seen: list[str] = []

    def run(
        self,
        case: BenchmarkCase,
        config: BenchConfig,
        sandbox: ReplaySandbox,
        caps: Caps,
        record_id: str,
    ) -> ProcessResult:
        self.seen.append(case.case_id)
        return ProcessResult(argv=("sq",), returncode=0, stdout="", stderr="")


def test_a_mixed_case_set_runs_judges_and_reports_each_kind_apart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(case_runners, "_RUNNERS", {})
    fix_runner, slice_runner = _Runner("fix"), _Runner("P6")
    register_case_runner(CaseKind.FIX, fix_runner)  # type: ignore[arg-type]
    register_case_runner(CaseKind.SLICE, slice_runner)  # type: ignore[arg-type]
    world = make_world(tmp_path, samples=1)
    fix_case = world.add_case("a fix")
    slice_case = as_slice(world, world.add_case("a slice"))
    sandbox = SandboxDouble(tmp_path / "sbx", "sandbox-1", make_tools_dir(tmp_path), detached=True)

    # runs: every (case, config) goes to the runner of the case's own kind
    for case in world.cases.values():
        runner = case_runner_for(case.kind)
        assert runner is not None
        for config in (CONFIG,):
            runner.run(case, config, sandbox, CAPS, "implreplay-x")  # type: ignore[arg-type]
    assert fix_runner.seen == [fix_case.case_id]
    assert slice_runner.seen == [slice_case.case_id]

    # grade records: stored by the fixture helper for both kinds, so the report has grades to read
    fix_ids = [world.add_sample(fix_case, cfg, 0) for cfg in (OPUS, SOL)]
    slice_ids = [world.add_sample(slice_case, cfg, 0) for cfg in (OPUS, SOL)]
    assert len(world.grades) == 4 and fix_ids and slice_ids

    # judges: only the slice case has pairs; the fix case is never judged
    store = _slice_store(tmp_path)
    plan = plan_judge(
        run=world.run,
        cases=world.cases,
        replays=world.replays,
        judge=JUDGE,
        limit=400000,
        max_cost=8.0,
        judge_cost=0.04,
        observed_cost=None,
        recorded_ids=(),
        repo_projects={world.cases[slice_case.case_id].project_id.value},
        reference_diff_for=lambda case: diff_text("reference"),
        diff_of=lambda ref: diff_text("any"),
    )
    assert [cp.case.case_id for cp in plan.cases] == [slice_case.case_id]
    dispatcher = ScriptedDispatcher()
    result = run_judging(
        plan,
        store=store,
        sidecars=MemorySidecars(),
        dispatcher=dispatcher,
        timeout_s=5.0,
        lock_root=tmp_path / "locks",
        process_runner=SubprocessRunner(),
        print_line=lambda line: None,
        clock=lambda: NOW,
    )
    assert result.status is JudgeStatus.COMPLETE and result.summary.judged == 3
    judgments = store.diff_judgments_for(plan.benchmark_id)
    assert {j.case_id for j in judgments} == {slice_case.case_id}

    # reports: each kind has its own tables, and only the slice case has a pairwise section
    report = world.build(judgments=judgments)
    text = render_text(report)
    assert [section.kind for section in report.tables] == [CaseKind.FIX, CaseKind.SLICE]
    assert text.index("objective grade") < text.index("slice cases") < text.index("pairwise (judge")
    assert report.pairwise is not None
    assert {row.label for row in report.pairwise.configs} == {"opus", "sol"}
    assert "pairwise" in render_json(report)

    # yield: both kinds' rows for the project
    project = PROJECT.value
    slice_records = [
        qualification(),
        qualification(
            QualificationOutcome.REJECTED, index=404, rejection=SliceCandidateRejection.NO_CODE_CHANGE
        ),
    ]
    fixes = [fix_record(project, "a", QualificationOutcome.QUALIFIED, case_id=fix_case.case_id)]
    yield_report = build_yield(fixes, [], 3, 0.1, slice_qualifications=slice_records)
    yield_output = yield_text(yield_report)
    assert project in yield_output and "slice cases" in yield_output
    assert "no_code_change 1" in yield_output
    assert [row["project"] for row in json.loads(yield_json(yield_report))["slice_cases"]] == [project]


def _slice_store(tmp_path: Path) -> SliceCaseRecordStore:
    return SliceCaseRecordStore(
        BenchmarkRecordStore(MetrologyStore(store_dir=tmp_path / "judge-store"))
    )
