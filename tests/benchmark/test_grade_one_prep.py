"""``grade_one``: review, restoration and reinstall (slice 425 Task 25, D1, D5, D9)."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import pytest

from squadron.benchmark.adapter import EnvironmentFailureReason, EnvironmentResolutionError
from squadron.benchmark.grade_budget import GradeCapReached, ReviewBudget
from squadron.benchmark.grade_one import grade_one
from squadron.benchmark.grade_prepare import prepare_tree
from squadron.benchmark.grade_review import ReviewFailed
from squadron.benchmark.grading_adapter import GradingAdapter
from squadron.metrology.benchmark_replay_enums import AbsenceClass
from squadron.metrology.grade_models import DETAIL_MAX_CHARS, GradeAbsence, ReviewOutcome
from squadron.metrology.grade_records import ImplementationGrade
from squadron.review.models import Severity
from tests.benchmark.grade_support import (
    LoggingAdapter,
    LoggingBudget,
    World,
    make_world,
    seed_reference,
)
from tests.benchmark.grading_fixtures import GradingRepo, build_tree_with, build_variant
from tests.benchmark.test_grade_identity import finding

START_PYPROJECT_RUFF = "line-length = 100"


def outcome(cost: float | None = 0.3, count: int = 1) -> ReviewOutcome:
    return ReviewOutcome(
        findings=tuple(finding(Severity.CONCERN, i) for i in range(count)),
        unnormalized_count=0,
        cost_usd=cost,
        rules_hash=None,
    )


def world_with(
    tmp_path: Path, repo: GradingRepo, log: list[str] | None = None, **kwargs: object
) -> World:
    shared: list[str] = [] if log is None else log

    def reviewer(tree: Path, base: str) -> ReviewOutcome:
        shared.append("review")
        return outcome()

    options: dict[str, object] = {
        "reviewer": reviewer,
        "budget": LoggingBudget(shared),
        "adapter": lambda: LoggingAdapter(shared),
    }
    options.update(kwargs)
    world = make_world(tmp_path, repo, **options)  # type: ignore[arg-type]
    world.factory.log = shared
    # A replay reads its case's reference before the review (D8), so one exists here.
    seed_reference(world, ())
    return world


def prepare(world: World, diff: bytes) -> list[str]:
    with world.factory(world.case) as sandbox:
        prepare_tree(world.run(world.replay_target(diff), sandbox))
    return world.factory.log


def test_the_steps_run_in_d1_order(tmp_path: Path, grading_repo: GradingRepo) -> None:
    world = world_with(tmp_path, grading_repo)
    producer = build_variant(grading_repo, "producer_c", tmp_path / "c")
    assert prepare(world, producer.diff()) == [
        "budget_check",
        "review",
        "budget_charge",
        "restore",
        "deps_changed",
        "reinstall",
    ]


def test_a_dependency_change_in_the_lock_alone_triggers_the_reinstall(
    tmp_path: Path, grading_repo: GradingRepo
) -> None:
    world = world_with(tmp_path, grading_repo)
    relocked = build_tree_with(grading_repo, "lock", {"uv.lock": "version = 1\n"}, tmp_path / "lock")
    assert prepare(world, relocked.diff())[-2:] == ["deps_changed", "reinstall"]


def test_no_dependency_change_means_no_reinstall(tmp_path: Path, grading_repo: GradingRepo) -> None:
    world = world_with(tmp_path, grading_repo)
    producer = build_variant(grading_repo, "producer_a", tmp_path / "a")
    assert "reinstall" not in prepare(world, producer.diff())


def lockfile_after(world: World, diff: bytes) -> str | None:
    with world.factory(world.case) as sandbox:
        run = world.run(world.replay_target(diff), sandbox)
        prepare_tree(run)
        return run.lockfile_sha256


def test_the_lockfile_hash_is_recorded_with_and_without_a_reinstall_and_none_without_a_lock(
    tmp_path: Path, grading_repo: GradingRepo
) -> None:
    lock_text = "version = 1\n# producer\n"
    expected = hashlib.sha256(lock_text.encode()).hexdigest()
    with_reinstall = build_tree_with(grading_repo, "l1", {"uv.lock": lock_text}, tmp_path / "l1")
    assert lockfile_after(world_with(tmp_path / "w1", grading_repo), with_reinstall.diff()) == expected

    no_lock = build_variant(grading_repo, "producer_a", tmp_path / "a")
    assert lockfile_after(world_with(tmp_path / "w2", grading_repo), no_lock.diff()) is None


@pytest.mark.parametrize(
    "reason",
    [
        EnvironmentFailureReason.LOCK_STALE_OR_UNRESOLVABLE,
        EnvironmentFailureReason.NO_LOCKFILE,
        EnvironmentFailureReason.LOCKFILE_UNSUPPORTED,
    ],
)
def test_an_unresolvable_producer_tree_is_a_config_absence(
    tmp_path: Path,
    grading_repo: GradingRepo,
    reason: EnvironmentFailureReason,
    caplog: pytest.LogCaptureFixture,
) -> None:
    error = EnvironmentResolutionError(reason, "the lock does not match")
    world = world_with(tmp_path, grading_repo, reinstall_error=error)
    producer = build_variant(grading_repo, "producer_c", tmp_path / "c")
    with caplog.at_level(logging.ERROR):
        record = grade_one(world.case, world.replay_target(producer.diff()), world.deps)
    assert isinstance(record, ImplementationGrade)
    assert record.absence is GradeAbsence.PRODUCER_ENV_UNRESOLVABLE
    assert record.absence_class is AbsenceClass.CONFIG
    assert any(reason.value in r.getMessage() for r in caplog.records if r.levelno == logging.ERROR)


def test_a_long_environment_error_is_recorded_not_raised(
    tmp_path: Path, grading_repo: GradingRepo
) -> None:
    """uv's stderr can run to pages; the absence keeps its tail within the record's cap."""
    stderr = "resolver noise\n" * 400 + "error: the lock does not match"
    error = EnvironmentResolutionError(EnvironmentFailureReason.LOCK_STALE_OR_UNRESOLVABLE, stderr)
    world = world_with(tmp_path, grading_repo, reinstall_error=error)
    producer = build_variant(grading_repo, "producer_c", tmp_path / "c")

    record = grade_one(world.case, world.replay_target(producer.diff()), world.deps)

    assert isinstance(record, ImplementationGrade)
    assert record.absence is GradeAbsence.PRODUCER_ENV_UNRESOLVABLE
    assert record.detail is not None and len(record.detail) <= DETAIL_MAX_CHARS
    assert record.detail.endswith("error: the lock does not match")


def test_a_malformed_producer_pyproject_is_a_config_absence(
    tmp_path: Path, grading_repo: GradingRepo, caplog: pytest.LogCaptureFixture
) -> None:
    world = world_with(tmp_path, grading_repo)
    broken = build_tree_with(grading_repo, "bad", {"pyproject.toml": "[project\n"}, tmp_path / "bad")
    with caplog.at_level(logging.ERROR):
        record = grade_one(world.case, world.replay_target(broken.diff()), world.deps)
    assert isinstance(record, ImplementationGrade)
    assert record.absence is GradeAbsence.PRODUCER_ENV_UNRESOLVABLE
    assert record.absence_class is AbsenceClass.CONFIG
    assert any("pyproject.toml" in r.getMessage() for r in caplog.records if r.levelno == logging.ERROR)


@pytest.mark.parametrize(
    "reason", [EnvironmentFailureReason.INSTALL_TIMEOUT, EnvironmentFailureReason.INSTALLER_MISSING]
)
def test_a_reinstall_timeout_or_missing_uv_is_a_harness_absence(
    tmp_path: Path,
    grading_repo: GradingRepo,
    reason: EnvironmentFailureReason,
    caplog: pytest.LogCaptureFixture,
) -> None:
    error = EnvironmentResolutionError(reason, "gave up")
    world = world_with(tmp_path, grading_repo, reinstall_error=error)
    producer = build_variant(grading_repo, "producer_c", tmp_path / "c")
    with caplog.at_level(logging.ERROR):
        record = grade_one(world.case, world.replay_target(producer.diff()), world.deps)
    assert isinstance(record, ImplementationGrade)
    assert record.absence is GradeAbsence.ENVIRONMENT_FAILED
    assert record.absence_class is AbsenceClass.HARNESS
    assert any(r.levelno == logging.ERROR for r in caplog.records)


def test_a_failed_review_stops_before_any_test_run(
    tmp_path: Path, grading_repo: GradingRepo, caplog: pytest.LogCaptureFixture
) -> None:
    def failing(tree: Path, base: str) -> ReviewOutcome:
        raise ReviewFailed("the review timed out")

    world = world_with(tmp_path, grading_repo, reviewer=failing)
    producer = build_variant(grading_repo, "producer_a", tmp_path / "a")
    with caplog.at_level(logging.ERROR):
        record = grade_one(world.case, world.replay_target(producer.diff()), world.deps)
    assert isinstance(record, ImplementationGrade)
    assert record.absence is GradeAbsence.REVIEW_FAILED
    assert not any(entry.startswith("suite") for entry in world.factory.log)
    assert "restore" not in world.factory.log
    assert any("timed out" in r.getMessage() for r in caplog.records if r.levelno == logging.ERROR)


def test_the_review_sees_the_tree_as_the_producer_wrote_it(
    tmp_path: Path, grading_repo: GradingRepo
) -> None:
    seen: list[str] = []

    def inspecting(tree: Path, base: str) -> ReviewOutcome:
        seen.append((tree / "pyproject.toml").read_text(encoding="utf-8"))
        return outcome()

    world = world_with(tmp_path, grading_repo, reviewer=inspecting)
    producer = build_variant(grading_repo, "producer_c", tmp_path / "c")
    with world.factory(world.case) as sandbox:
        prepare_tree(world.run(world.replay_target(producer.diff()), sandbox))
        # ... and afterwards the config is the start commit's again.
        restored = (sandbox.tree / "pyproject.toml").read_text(encoding="utf-8")
    assert "line-length = 200" in seen[0]
    assert "line-length = 100" in restored


def test_a_budget_at_its_cap_raises_before_any_review_and_writes_no_record(
    tmp_path: Path, grading_repo: GradingRepo
) -> None:
    budget = ReviewBudget(cap_usd=1.0, per_review_usd=0.2)
    budget.after_review(1.5)
    world = make_world(tmp_path, grading_repo, budget=budget)
    seed_reference(world, ())
    producer = build_variant(grading_repo, "producer_a", tmp_path / "a")
    with pytest.raises(GradeCapReached):
        grade_one(world.case, world.replay_target(producer.diff()), world.deps)
    assert world.store.grades_for("bench-1") == []


@pytest.mark.parametrize(
    ("reported", "charged", "unpriced"), [(0.4, 0.4, 0), (None, 0.2, 1)], ids=["priced", "unpriced"]
)
def test_a_failed_review_is_charged_to_the_budget(
    tmp_path: Path,
    grading_repo: GradingRepo,
    reported: float | None,
    charged: float,
    unpriced: int,
) -> None:
    def failing(tree: Path, base: str) -> ReviewOutcome:
        raise ReviewFailed("the review returned nothing", reported)

    budget = ReviewBudget(cap_usd=10.0, per_review_usd=0.2)
    world = make_world(tmp_path, grading_repo, reviewer=failing, budget=budget)
    seed_reference(world, ())
    producer = build_variant(grading_repo, "producer_a", tmp_path / "a")
    record = grade_one(world.case, world.replay_target(producer.diff()), world.deps)
    assert isinstance(record, ImplementationGrade)
    assert record.absence is GradeAbsence.REVIEW_FAILED
    assert budget.spent == pytest.approx(charged)
    assert budget.unpriced == unpriced
    # The record carries what was reported, never the budget's stand-in figure.
    assert record.grading_cost_usd == reported


def test_the_reviews_cost_reaches_the_budget_and_the_record(
    tmp_path: Path, grading_repo: GradingRepo
) -> None:
    error = EnvironmentResolutionError(EnvironmentFailureReason.LOCK_STALE_OR_UNRESOLVABLE, "stale")
    world = make_world(
        tmp_path,
        grading_repo,
        reviewer=lambda tree, base: outcome(cost=0.3),
        reinstall_error=error,
    )
    seed_reference(world, ())
    producer = build_variant(grading_repo, "producer_c", tmp_path / "c")
    record = grade_one(world.case, world.replay_target(producer.diff()), world.deps)
    assert isinstance(record, ImplementationGrade)
    assert record.grading_cost_usd == pytest.approx(0.3)
    assert world.deps.budget.spent == pytest.approx(0.3)
    assert world.deps.budget.unpriced == 0


def test_an_unpriced_review_counts_at_the_per_review_figure_but_not_in_the_record(
    tmp_path: Path, grading_repo: GradingRepo
) -> None:
    error = EnvironmentResolutionError(EnvironmentFailureReason.LOCK_STALE_OR_UNRESOLVABLE, "stale")
    world = make_world(
        tmp_path,
        grading_repo,
        reviewer=lambda tree, base: outcome(cost=None),
        reinstall_error=error,
    )
    seed_reference(world, ())
    producer = build_variant(grading_repo, "producer_c", tmp_path / "c")
    record = grade_one(world.case, world.replay_target(producer.diff()), world.deps)
    assert isinstance(record, ImplementationGrade)
    assert record.grading_cost_usd is None
    assert world.deps.budget.spent == pytest.approx(0.2)
    assert world.deps.budget.unpriced == 1


def test_the_findings_sidecar_and_summary_are_kept(tmp_path: Path, grading_repo: GradingRepo) -> None:
    world = world_with(tmp_path, grading_repo)
    producer = build_variant(grading_repo, "producer_a", tmp_path / "a")
    with world.factory(world.case) as sandbox:
        run = world.run(world.replay_target(producer.diff()), sandbox)
        prepare_tree(run)
    (summary,) = run.review_summaries
    assert summary.total == 1
    assert world.store.reviews.get(summary.findings_sha256)


def test_protocol_conformance_of_the_logging_adapter() -> None:
    assert isinstance(LoggingAdapter([]), GradingAdapter)
