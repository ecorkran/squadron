"""``run_grading``: resume, retry-harness and the estimate (slice 425 Task 36, D9, D15, D16)."""

from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path

import pytest

from squadron.benchmark.grade_estimate import EstimateInputs
from squadron.benchmark.grade_plan import GradePlan
from squadron.benchmark.grade_runner import GradeStatus, GradeSummary, run_grading
from squadron.core.process_runner import SubprocessRunner
from squadron.metrology.benchmark_models import BenchmarkCase
from squadron.metrology.benchmark_replay_enums import AbsenceClass
from squadron.metrology.benchmark_replay_models import BenchmarkRun, ImplementationReplay
from squadron.metrology.errors import MetrologyStoreError
from squadron.metrology.grade_models import GradeAbsence
from tests.benchmark.grade_support import World, make_world
from tests.benchmark.grading_fixtures import GradingRepo
from tests.benchmark.test_grade_plan import make_replay, make_run, plan
from tests.benchmark.test_grade_records import make_implementation, make_reference
from tests.benchmark.test_grade_runner import Calls, FakeGrader, run
from tests.metrology.test_benchmark_store import make_case

TARGET = 0.2


def replays_for_two_configs(
    cases: list[BenchmarkCase], samples: int = 3
) -> list[tuple[str, ImplementationReplay]]:
    out: list[tuple[str, ImplementationReplay]] = []
    for case in cases:
        for alias in ("opus", "sol"):
            for sample in range(samples):
                record_id, replay = make_replay(case, sample)
                config = replay.config.model_copy(update={"alias": alias, "model": f"{alias}-model"})
                out.append((f"{record_id}-{alias}", replay.model_copy(update={"config": config})))
    return out


def estimate_inputs(
    run_record: BenchmarkRun,
    cases: list[BenchmarkCase],
    replays: list[tuple[str, ImplementationReplay]],
) -> EstimateInputs:
    return EstimateInputs(
        run=run_record, case_ids=[c.case_id for c in cases], replays=replays, target_difference=TARGET
    )


def start(
    tmp_path: Path, repo: GradingRepo, cases: list[BenchmarkCase], replays, **plan_kwargs: object
) -> tuple[World, GradePlan]:
    world = make_world(tmp_path, repo)
    return world, plan(world.store, cases, replays, **plan_kwargs)  # type: ignore[arg-type]


def grade(
    world: World, grade_plan: GradePlan, tmp_path: Path, **kwargs: object
) -> tuple[GradeSummary, Calls, list[str]]:
    calls: Calls = []
    lines: list[str] = []
    grader = FakeGrader(world, calls, on_call=kwargs.pop("on_call", None))  # type: ignore[arg-type]
    summary = run(world, grade_plan, grader, lines, tmp_path / "locks")
    return summary, calls, lines


def test_a_second_run_grades_nothing_new(tmp_path: Path, grading_repo: GradingRepo) -> None:
    case = make_case()
    replays = [make_replay(case, 0), make_replay(case, 1)]
    world, first_plan = start(tmp_path, grading_repo, [case], replays)
    _, first_calls, _ = grade(world, first_plan, tmp_path)
    assert len(first_calls) == 3  # one reference and two replays

    second_plan = plan(world.store, [case], replays)
    assert (second_plan.references, second_plan.replays) == ((), ())
    _, second_calls, lines = grade(world, second_plan, tmp_path)
    assert second_calls == []
    assert "nothing to grade" in lines[0]


def test_a_harness_absent_grade_is_skipped_then_retried_and_the_deleted_count_is_reported(
    tmp_path: Path, grading_repo: GradingRepo
) -> None:
    case = make_case()
    record_id, replay = make_replay(case, 0)
    world, base = start(tmp_path, grading_repo, [case], [(record_id, replay)])
    grader_identity = base.grader
    digest = replay.environment.identity_digest  # type: ignore[union-attr]
    world.store.write_grade(
        make_implementation(
            replay_id=record_id,
            grader=grader_identity,
            result=None,
            absence=GradeAbsence.REVIEW_FAILED,
            absence_class=AbsenceClass.HARNESS,
        )
    )
    world.store.write_reference_grade(
        make_reference(
            case_id=case.case_id,
            grader=grader_identity,
            environment_digest=digest,
            result=None,
            absence=GradeAbsence.ENVIRONMENT_FAILED,
            baseline_nodes=None,
            baseline_snapshot=None,
            review_floor=None,
        )
    )

    skipped = plan(world.store, [case], [(record_id, replay)])
    assert (skipped.references, skipped.replays) == ((), ())

    retried = plan(world.store, [case], [(record_id, replay)], retry_harness=True)
    summary, calls, lines = grade(world, retried, tmp_path)
    assert summary.deleted_stale == 2
    assert any("removed 2 harness-absent grade records" in line for line in lines)
    assert [kind for kind, _ in calls] == ["reference", "replay"]  # the reference graded again
    stored = [g for _, g in world.store.grades_for("bench-3f9c")]
    assert [g.absence for g in stored] == [None]


def test_an_interrupted_grade_leaves_no_record_and_the_rerun_grades_it(
    tmp_path: Path, grading_repo: GradingRepo
) -> None:
    case = make_case()
    replays = [make_replay(case, 0)]
    world, first_plan = start(tmp_path, grading_repo, [case], replays)

    def die_on_the_replay(count: int) -> None:
        if count == 2:
            raise RuntimeError("killed mid-grade")

    with pytest.raises(RuntimeError, match="killed"):
        grade(world, first_plan, tmp_path, on_call=die_on_the_replay)
    assert world.store.grades_for("bench-3f9c") == []

    rerun = plan(world.store, [case], replays)
    assert rerun.references == ()  # the reference finished before the interruption
    assert len(rerun.replays) == 1
    _, calls, _ = grade(world, rerun, tmp_path)
    assert [kind for kind, _ in calls] == ["replay"]
    assert len(world.store.grades_for("bench-3f9c")) == 1


def test_the_estimate_is_written_for_two_configs_at_k_three_with_enough_cases(
    tmp_path: Path, grading_repo: GradingRepo
) -> None:
    cases = [make_case(task=f"t{i}") for i in range(5)]
    replays = replays_for_two_configs(cases)
    world, grade_plan = start(tmp_path, grading_repo, cases, replays)
    calls: Calls = []
    lines: list[str] = []
    summary = run_grading(
        grade_plan,
        lambda budget: replace(world.deps, budget=budget, grader=grade_plan.grader),
        lock_root=tmp_path / "locks",
        process_runner=SubprocessRunner(),
        print_line=lines.append,
        grade=FakeGrader(world, calls),
        estimate=estimate_inputs(make_run(), cases, replays),
    )
    assert summary.status is GradeStatus.COMPLETE
    assert summary.estimate_note is not None and "written" in summary.estimate_note
    stored = world.store.latest_estimate("fixes")
    assert stored is not None
    assert (stored.n_cases, stored.samples, len(stored.pairs)) == (5, 3, 1)
    assert stored.grader_digest == grade_plan.grader.digest


@pytest.mark.parametrize(
    ("case_count", "configs", "samples", "reason"),
    [
        (4, 2, 3, "4 included cases"),
        (5, 1, 3, "two configs"),
        (5, 2, 1, "1 sample per case"),
    ],
)
def test_nothing_is_written_and_the_summary_names_the_reason(
    tmp_path: Path,
    grading_repo: GradingRepo,
    case_count: int,
    configs: int,
    samples: int,
    reason: str,
) -> None:
    cases = [make_case(task=f"t{i}") for i in range(case_count)]
    replays = [
        item
        for item in replays_for_two_configs(cases, samples=samples)
        if configs == 2 or "-opus" in item[0]
    ]
    world, grade_plan = start(tmp_path, grading_repo, cases, replays)
    inputs = estimate_inputs(make_run().model_copy(update={"samples": samples}), cases, replays)
    summary = run_grading(
        grade_plan,
        lambda budget: replace(world.deps, budget=budget, grader=grade_plan.grader),
        lock_root=tmp_path / "locks",
        process_runner=SubprocessRunner(),
        print_line=lambda line: None,
        grade=FakeGrader(world, []),
        estimate=inputs,
    )
    assert summary.estimate_note is not None
    assert reason in summary.estimate_note
    assert world.store.latest_estimate("fixes") is None


def test_a_store_write_failure_stops_the_run_with_an_error_log(
    tmp_path: Path, grading_repo: GradingRepo, caplog: pytest.LogCaptureFixture
) -> None:
    case = make_case()
    world, grade_plan = start(tmp_path, grading_repo, [case], [make_replay(case, 0)])
    inner = world.store._store  # pyright: ignore[reportPrivateUsage]

    def boom(record_id: str, record: object) -> None:
        raise MetrologyStoreError("disk full")

    inner.write_record = boom  # type: ignore[method-assign]
    with caplog.at_level(logging.ERROR), pytest.raises(MetrologyStoreError, match="disk full"):
        grade(world, grade_plan, tmp_path)
    assert any("Failed to write grade record" in r.getMessage() for r in caplog.records)
    assert not list((tmp_path / "locks").glob("*.lock"))  # the lock is released


def test_the_summary_counts_outcomes_and_absence_kinds(
    tmp_path: Path, grading_repo: GradingRepo
) -> None:
    case = make_case()
    world, grade_plan = start(tmp_path, grading_repo, [case], [make_replay(case, 0)])
    summary, _, _ = grade(world, grade_plan, tmp_path)
    assert summary.references_graded == 1
    assert summary.replays_graded == 1
    assert summary.passed == 2
    assert summary.failed == 0
    assert sum(summary.absences.values()) == 0
