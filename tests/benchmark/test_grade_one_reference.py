"""``grade_one`` for a reference: baseline, floor and its own pass (slice 425 Task 30, D8)."""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from squadron.benchmark.adapter import NodeOutcome
from squadron.benchmark.grade_budget import GradeCapReached, ReviewBudget
from squadron.benchmark.grade_one import grade_one
from squadron.benchmark.grade_review import ReviewFailed
from squadron.metrology.benchmark_models import BenchmarkCase, GraderCommand, GraderCommandKind
from squadron.metrology.benchmark_replay_enums import AbsenceClass
from squadron.metrology.grade_models import GradeAbsence, ReviewOutcome
from squadron.metrology.grade_records import ReferenceGrade
from squadron.metrology.snapshot_models import CodeSnapshot
from squadron.review.models import Severity
from tests.benchmark.grade_support import (
    OTHER_ENVIRONMENT,
    World,
    default_snapshot,
    make_world,
    passing_suite,
)
from tests.benchmark.grading_fixtures import HIDDEN_IDS, GradingRepo, make_grading_case
from tests.benchmark.test_grade_identity import finding

START_IDS = ("t.py::a", "t.py::b")
SUITE = GraderCommand(kind=GraderCommandKind.SUITE, argv=("python", "-m", "pytest"))
LINT = GraderCommand(kind=GraderCommandKind.LINT, argv=("ruff", "check"))
TYPES = GraderCommand(kind=GraderCommandKind.TYPECHECK, argv=("pyright",))


def outcome(count: int, cost: float | None = 0.1) -> ReviewOutcome:
    return ReviewOutcome(
        findings=tuple(finding(Severity.CONCERN, i) for i in range(count)),
        unnormalized_count=0,
        cost_usd=cost,
        rules_hash=None,
    )


class FloorReviewer:
    """Returns a scripted number of findings per call; records each call's tree HEAD."""

    def __init__(self, counts: list[int], fail_on: int | None = None) -> None:
        self._counts = counts
        self._fail_on = fail_on
        self.calls = 0

    def __call__(self, tree: Path, base: str) -> ReviewOutcome:
        self.calls += 1
        if self.calls == self._fail_on:
            raise ReviewFailed("the review timed out")
        return outcome(self._counts[self.calls - 1])


def reference_world(tmp_path: Path, repo: GradingRepo, **kwargs: object) -> World:
    options: dict[str, object] = {
        "reviewer": FloorReviewer([2, 4, 3]),
        "suites": passing_suite(),
        "collect": lambda sandbox, case: START_IDS,
    }
    options.update(kwargs)
    return make_world(tmp_path, repo, **options)  # type: ignore[arg-type]


def head_of(tree: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tree, capture_output=True, text=True, check=True
    ).stdout.strip()


def test_baseline_sidecars_are_taken_before_the_diff_applies(
    tmp_path: Path, grading_repo: GradingRepo
) -> None:
    heads: list[str] = []

    def measure(tree: Path, case: BenchmarkCase, head: str) -> CodeSnapshot:
        heads.append(head_of(tree))
        return default_snapshot(tree, case, head)

    case = make_grading_case(grading_repo, grader_commands=(SUITE, LINT, TYPES))
    world = reference_world(tmp_path, grading_repo, measure=measure, case=case)
    record = grade_one(world.case, world.reference_target(), world.deps)
    assert isinstance(record, ReferenceGrade)
    assert heads[0] == grading_repo.start_sha  # the baseline snapshot: diff not yet applied
    assert heads[1] != grading_repo.start_sha  # the reference's own snapshot: diff committed
    assert record.baseline_nodes is not None
    assert json.loads(world.store.nodes.get(record.baseline_nodes)) == list(START_IDS)
    assert record.baseline_snapshot is not None
    assert world.store.snapshots.get(record.baseline_snapshot.sha256)
    assert (record.baseline_lint_total, record.baseline_type_total) == (4, 2)


def test_the_floor_runs_review_floor_runs_times_and_reduces_their_findings(
    tmp_path: Path, grading_repo: GradingRepo
) -> None:
    reviewer = FloorReviewer([2, 4, 3])
    world = reference_world(tmp_path, grading_repo, reviewer=reviewer)
    record = grade_one(world.case, world.reference_target(), world.deps)
    assert isinstance(record, ReferenceGrade)
    assert reviewer.calls == world.deps.grader.review_floor_runs == 3
    assert record.review_floor is not None
    assert (record.review_floor.min, record.review_floor.max, record.review_floor.mean) == (2, 4, 3.0)
    assert record.result is not None
    assert len(record.result.reviews) == 3
    assert record.grading_cost_usd == pytest.approx(0.3)


def test_one_failing_floor_run_is_review_failed_with_no_floor(
    tmp_path: Path, grading_repo: GradingRepo, caplog: pytest.LogCaptureFixture
) -> None:
    world = reference_world(tmp_path, grading_repo, reviewer=FloorReviewer([2, 4, 3], fail_on=2))
    with caplog.at_level(logging.ERROR):
        record = grade_one(world.case, world.reference_target(), world.deps)
    assert isinstance(record, ReferenceGrade)
    assert record.absence is GradeAbsence.REVIEW_FAILED
    assert record.review_floor is None
    assert record.result is None
    assert any(r.levelno == logging.ERROR for r in caplog.records)


def test_a_cap_reached_after_the_second_floor_run_stops_before_the_third(
    tmp_path: Path, grading_repo: GradingRepo
) -> None:
    budget = ReviewBudget(cap_usd=0.15, per_review_usd=0.1)
    reviewer = FloorReviewer([2, 4, 3])
    world = reference_world(tmp_path, grading_repo, reviewer=reviewer, budget=budget)
    with pytest.raises(GradeCapReached):
        grade_one(world.case, world.reference_target(), world.deps)
    assert reviewer.calls == 2
    assert world.store.grades_for("bench-1") == []
    assert (
        world.store.get_reference_grade(
            world.case.case_id,
            world.deps.grader.digest,
            world.factory.identity.identity_digest,
        )
        is None
    )


def test_a_hidden_failure_on_the_reference_is_reference_failed_grade(
    tmp_path: Path, grading_repo: GradingRepo, caplog: pytest.LogCaptureFixture
) -> None:
    failing = "tests/review/test_sqhidden_test_parts.py::TestWorstVerdict::test_fail_outranks_unknown"
    world = reference_world(
        tmp_path, grading_repo, suites=passing_suite(outcomes={failing: NodeOutcome.FAILED})
    )
    with caplog.at_level(logging.ERROR):
        record = grade_one(world.case, world.reference_target(), world.deps)
    assert isinstance(record, ReferenceGrade)
    assert record.absence is GradeAbsence.REFERENCE_FAILED_GRADE
    assert record.result is None
    assert "1 of 3 hidden tests" in (record.detail or "")
    assert failing in (record.detail or "")  # the failing id is named for diagnosis
    assert record.baseline_nodes is not None  # what it measured is kept beside the absence
    assert record.review_floor is not None
    from squadron.metrology.grade_models import GRADE_ABSENCE_CLASS

    assert GRADE_ABSENCE_CLASS[GradeAbsence.REFERENCE_FAILED_GRADE] is AbsenceClass.HARNESS
    assert any(r.levelno == logging.ERROR for r in caplog.records)


def test_a_passing_reference_passes_every_hidden_test_with_no_regressions(
    tmp_path: Path, grading_repo: GradingRepo
) -> None:
    world = reference_world(tmp_path, grading_repo)
    record = grade_one(world.case, world.reference_target(), world.deps)
    assert isinstance(record, ReferenceGrade)
    assert record.result is not None
    assert record.result.passed
    assert record.result.hidden_total == len(HIDDEN_IDS)
    assert record.result.regression_failure_count == 0


def test_a_reference_is_written_once_per_case_grader_and_environment(
    tmp_path: Path, grading_repo: GradingRepo
) -> None:
    world = reference_world(tmp_path, grading_repo)
    record = grade_one(world.case, world.reference_target(), world.deps)
    digest = world.factory.identity.identity_digest
    assert (
        world.store.get_reference_grade(world.case.case_id, world.deps.grader.digest, digest) == record
    )

    other_world = reference_world(tmp_path / "other", grading_repo, identity=OTHER_ENVIRONMENT)
    other_world.deps = replace(other_world.deps, store=world.store)
    other = grade_one(
        other_world.case, other_world.reference_target(OTHER_ENVIRONMENT), other_world.deps
    )
    assert isinstance(other, ReferenceGrade)
    assert other.environment_digest == OTHER_ENVIRONMENT.identity_digest
    grader = world.deps.grader.digest
    assert (
        world.store.get_reference_grade(world.case.case_id, grader, OTHER_ENVIRONMENT.identity_digest)
        == other
    )
    assert world.store.get_reference_grade(world.case.case_id, grader, digest) == record


def test_the_baseline_keeps_collection_order_not_alphabetical_order(
    tmp_path: Path, grading_repo: GradingRepo
) -> None:
    """Tests that depend on the order within their file must run in it (found live, Task 31)."""
    unsorted = ("t.py::test_z_first", "t.py::test_a_second")
    world = reference_world(tmp_path, grading_repo, collect=lambda sandbox, case: unsorted)
    record = grade_one(world.case, world.reference_target(), world.deps)
    assert isinstance(record, ReferenceGrade)
    assert record.baseline_nodes is not None
    assert json.loads(world.store.nodes.get(record.baseline_nodes)) == list(unsorted)
