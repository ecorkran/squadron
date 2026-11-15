"""``run_grading``: bound, order, cap and lock (slice 425 Task 35, D8, D9)."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import replace
from pathlib import Path

import pytest

from squadron.benchmark.bench_lock import BenchmarkLock
from squadron.benchmark.grade_budget import GradeCapReached, ReviewBudget
from squadron.benchmark.grade_deps import GradeDeps, GradeTarget
from squadron.benchmark.grade_one import GradeRecord
from squadron.benchmark.grade_plan import GradePlan, GradeRefusal
from squadron.benchmark.grade_runner import GRADE_LOCK_SUFFIX, GradeStatus, run_grading
from squadron.core.process_runner import SubprocessRunner
from squadron.metrology.benchmark_models import BenchmarkCase
from squadron.metrology.benchmark_replay_models import ImplementationReplay
from squadron.metrology.grade_models import GradeAbsence, GradeSubject
from squadron.metrology.grade_records import ImplementationGrade, ReferenceGrade
from tests.benchmark.grade_support import World, make_world
from tests.benchmark.grading_fixtures import GradingRepo
from tests.benchmark.test_grade_models import make_result
from tests.benchmark.test_grade_plan import make_replay, plan
from tests.benchmark.test_grade_records import make_implementation, make_reference
from tests.metrology.test_benchmark_store import make_case

Calls = list[tuple[str, str]]


class FakeGrader:
    """A ``grade_one`` double: records its calls and writes records the way ``grade_one`` does."""

    def __init__(
        self,
        world: World,
        calls: Calls,
        *,
        failing_references: Callable[[BenchmarkCase], str] | None = None,
        on_call: Callable[[int], None] | None = None,
    ) -> None:
        self._world = world
        self._calls = calls
        self._failing = failing_references
        self._on_call = on_call
        self.count = 0

    def __call__(
        self, case: BenchmarkCase, target: GradeTarget, deps: GradeDeps
    ) -> ReferenceGrade | ImplementationGrade:
        self.count += 1
        if self._on_call is not None:
            self._on_call(self.count)
        store = deps.store
        if target.subject is GradeSubject.REFERENCE:
            self._calls.append(("reference", case.case_id))
            mode = self._failing(case) if self._failing else "pass"
            reference = self._reference(case, target, mode)
            store.write_reference_grade(reference)
            return reference
        self._calls.append(("replay", f"{case.case_id}:{target.replay_id}"))
        assert target.replay_id is not None
        grade = make_implementation(
            replay_id=target.replay_id,
            benchmark_id="bench-3f9c",
            case_id=case.case_id,
            grader=deps.grader,
        )
        store.write_grade(grade)
        return grade

    def _reference(self, case: BenchmarkCase, target: GradeTarget, mode: str) -> ReferenceGrade:
        grader = self._world.deps.grader
        common = {
            "case_id": case.case_id,
            "grader": grader,
            "environment_digest": target.environment_digest,
        }
        if mode == "absent":
            return make_reference(
                **common,
                result=None,
                absence=GradeAbsence.REFERENCE_FAILED_GRADE,
                baseline_nodes=None,
                baseline_snapshot=None,
                review_floor=None,
            )
        if mode == "fails":
            from squadron.benchmark.adapter import NodeOutcome, NodeResult

            failing = (NodeResult("t.py::x", NodeOutcome.FAILED),)
            return make_reference(
                **common, result=make_result(hidden_passed=2, hidden_failures=failing)
            )
        return make_reference(**common)


def setup(
    tmp_path: Path,
    repo: GradingRepo,
    cases: list[BenchmarkCase],
    replays: Sequence[tuple[str, ImplementationReplay]],
    **plan_kwargs: object,
) -> tuple[World, GradePlan]:
    world = make_world(tmp_path, repo)
    grade_plan = plan(world.store, cases, replays, **plan_kwargs)  # type: ignore[arg-type]
    return world, grade_plan


def run(
    world: World,
    grade_plan: GradePlan,
    grader: FakeGrader,
    lines: list[str],
    lock_root: Path,
):
    def make_deps(budget: ReviewBudget) -> GradeDeps:
        return replace(world.deps, budget=budget, grader=grade_plan.grader)

    return run_grading(
        grade_plan,
        make_deps,
        lock_root=lock_root,
        process_runner=SubprocessRunner(),
        print_line=lines.append,
        grade=grader,
    )


def two_config_replays(case: BenchmarkCase) -> list[tuple[str, ImplementationReplay]]:
    out: list[tuple[str, ImplementationReplay]] = []
    for sample in (1, 0):
        for alias in ("b-config", "a-config"):
            record_id, replay = make_replay(case, sample)
            record_id = f"{record_id}-{alias}"
            config = replay.config.model_copy(update={"alias": alias})
            out.append((record_id, replay.model_copy(update={"config": config})))
    return out


def test_the_bound_prints_before_the_first_grade(tmp_path: Path, grading_repo: GradingRepo) -> None:
    case = make_case()
    world, grade_plan = setup(tmp_path, grading_repo, [case], [make_replay(case, 0)])
    events: list[str] = []
    calls: Calls = []

    class Recording(FakeGrader):
        def __call__(self, c: BenchmarkCase, t: GradeTarget, d: GradeDeps) -> GradeRecord:
            events.append("grade")
            return super().__call__(c, t, d)

    run(world, grade_plan, Recording(world, calls), events, tmp_path / "locks")
    assert events[0].startswith("grade bench-3f9c")
    assert events.index("grade") > 0


def test_references_precede_their_replays_and_replays_run_sample_major(
    tmp_path: Path, grading_repo: GradingRepo
) -> None:
    case = make_case()
    world, grade_plan = setup(tmp_path, grading_repo, [case], two_config_replays(case))
    calls: Calls = []
    run(world, grade_plan, FakeGrader(world, calls), [], tmp_path / "locks")
    assert [kind for kind, _ in calls] == ["reference", "replay", "replay", "replay", "replay"]
    order = [detail.split(":")[1] for kind, detail in calls if kind == "replay"]
    assert [item[item.rindex("-s") + 1 :] for item in order] == [
        "s0-a-config",
        "s0-b-config",
        "s1-a-config",
        "s1-b-config",
    ]


@pytest.mark.parametrize("mode", ["absent", "fails"])
def test_a_failed_reference_drops_the_case_and_skips_its_replays(
    tmp_path: Path, grading_repo: GradingRepo, mode: str
) -> None:
    bad, good = make_case(task="bad"), make_case(task="good")
    replays = [make_replay(bad, 0), make_replay(good, 0)]
    world, grade_plan = setup(tmp_path, grading_repo, [bad, good], replays)
    calls: Calls = []
    lines: list[str] = []
    grader = FakeGrader(
        world, calls, failing_references=lambda c: mode if c.case_id == bad.case_id else "pass"
    )
    summary = run(world, grade_plan, grader, lines, tmp_path / "locks")
    graded_replays = [detail for kind, detail in calls if kind == "replay"]
    assert all(bad.case_id not in detail for detail in graded_replays)
    assert any(good.case_id in detail for detail in graded_replays)
    assert summary.dropped_cases == (bad.case_id,)
    assert any("dropped" in line and bad.case_id in line for line in lines)


def test_a_cap_reached_on_the_third_review_stops_the_run_and_keeps_every_record(
    tmp_path: Path, grading_repo: GradingRepo
) -> None:
    case = make_case()
    world, grade_plan = setup(tmp_path, grading_repo, [case], two_config_replays(case))
    calls: Calls = []

    def stop_on_third(count: int) -> None:
        if count == 3:
            raise GradeCapReached(1.0, 1.0)

    summary = run(
        world, grade_plan, FakeGrader(world, calls, on_call=stop_on_third), [], tmp_path / "locks"
    )
    assert summary.status is GradeStatus.CAP_REACHED
    assert len(calls) == 2  # the reference and the first replay were graded and written
    assert len(world.store.grades_for("bench-3f9c")) == 1
    assert (
        world.store.get_reference_grade(
            case.case_id, grade_plan.grader.digest, grade_plan.references[0].environment_digest
        )
        is not None
    )


def test_the_summary_reports_spent_and_unpriced_from_the_budget(
    tmp_path: Path, grading_repo: GradingRepo
) -> None:
    case = make_case()
    world, grade_plan = setup(tmp_path, grading_repo, [case], [make_replay(case, 0)])
    budgets: list[ReviewBudget] = []

    def charge(count: int) -> None:
        # The double has no budget of its own: it reads the one the runner built.
        budgets[0].after_review(0.4 if count == 1 else None)

    def make_deps(budget: ReviewBudget) -> GradeDeps:
        budgets.append(budget)
        return replace(world.deps, budget=budget, grader=grade_plan.grader)

    summary = run_grading(
        grade_plan,
        make_deps,
        lock_root=tmp_path / "locks",
        process_runner=SubprocessRunner(),
        print_line=lambda line: None,
        grade=FakeGrader(world, [], on_call=charge),
    )
    assert summary.spent_usd == pytest.approx(0.4 + grade_plan.per_review_usd)
    assert summary.unpriced_reviews == 1
    assert (summary.references_graded, summary.replays_graded, summary.passed) == (1, 1, 2)


def test_a_held_lock_refuses_naming_the_benchmark_and_leaves_the_holder_untouched(
    tmp_path: Path, grading_repo: GradingRepo
) -> None:
    case = make_case()
    world, grade_plan = setup(tmp_path, grading_repo, [case], [make_replay(case, 0)])
    lock_root = tmp_path / "locks"
    calls: Calls = []
    with BenchmarkLock.acquire(
        lock_root, f"{grade_plan.benchmark_id}{GRADE_LOCK_SUFFIX}", SubprocessRunner()
    ):
        holder = lock_root / f"{grade_plan.benchmark_id}{GRADE_LOCK_SUFFIX}.lock"
        before = holder.read_text()
        with pytest.raises(GradeRefusal, match=grade_plan.benchmark_id):
            run(world, grade_plan, FakeGrader(world, calls), [], lock_root)
        assert holder.read_text() == before
    assert calls == []
    assert not holder.exists()  # released by its owner, not by the refused run


def test_the_lock_is_released_when_the_run_ends(tmp_path: Path, grading_repo: GradingRepo) -> None:
    case = make_case()
    world, grade_plan = setup(tmp_path, grading_repo, [case], [make_replay(case, 0)])
    lock_root = tmp_path / "locks"
    run(world, grade_plan, FakeGrader(world, []), [], lock_root)
    assert not (lock_root / f"{grade_plan.benchmark_id}{GRADE_LOCK_SUFFIX}.lock").exists()
