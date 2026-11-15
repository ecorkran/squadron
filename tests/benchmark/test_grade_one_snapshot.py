"""``grade_one``: producer-new tests and the snapshot (slice 425 Task 26, D1, D2, D12)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from squadron.benchmark.adapter import (
    NodeOutcome,
    NodeResult,
    SuiteRun,
    SuiteRunError,
    SuiteSelection,
)
from squadron.benchmark.grade_checks import load_baseline, run_producer_new, take_snapshot
from squadron.benchmark.grade_deps import MissingReferenceGrade
from squadron.benchmark.grade_one import grade_one
from squadron.benchmark.grade_prepare import prepare_tree
from squadron.benchmark.grade_run import GradeRun
from squadron.benchmark.grade_snapshot import make_snapshot_measurer
from squadron.metrology.benchmark_models import BenchmarkCase, GraderCommand, GraderCommandKind
from squadron.metrology.benchmark_replay_enums import AbsenceClass
from squadron.metrology.grade_models import GradeAbsence, ReviewOutcome
from squadron.metrology.grade_records import ImplementationGrade
from squadron.metrology.snapshot.registry import default_registry
from squadron.metrology.snapshot_models import CodeSnapshot, SnapshotMetric, ToolIdentity
from tests.benchmark.grade_support import (
    World,
    default_snapshot,
    edit_measurement,
    make_world,
    quiet_review,
    seed_reference,
)
from tests.benchmark.grading_fixtures import GradingRepo, build_variant, make_grading_case
from tests.metrology.snapshot.conftest import FakeToolRunner

START_IDS = ("t.py::a", "t.py::b")
SUITE = GraderCommand(kind=GraderCommandKind.SUITE, argv=("python", "-m", "pytest"))
LINT = GraderCommand(kind=GraderCommandKind.LINT, argv=("ruff", "check"))
TYPES = GraderCommand(kind=GraderCommandKind.TYPECHECK, argv=("pyright",))


def recording_suite(seen: list[SuiteSelection], outcome: NodeOutcome = NodeOutcome.PASSED):
    def suite(selection: SuiteSelection) -> SuiteRun:
        seen.append(selection)
        ids = selection.node_ids or ()
        return SuiteRun(results=tuple(NodeResult(node_id=i, outcome=outcome) for i in ids))

    return suite


def build(tmp_path: Path, repo: GradingRepo, **kwargs: object) -> tuple[World, bytes]:
    commands = kwargs.pop("commands", (SUITE, LINT, TYPES))
    case = make_grading_case(repo, grader_commands=commands)  # type: ignore[arg-type]
    options: dict[str, object] = {"reviewer": quiet_review, "case": case}
    options.update(kwargs)
    world = make_world(tmp_path, repo, **options)  # type: ignore[arg-type]
    producer = build_variant(repo, "producer_a", tmp_path / "producer")
    return world, producer.diff()


def checks(world: World, diff: bytes) -> GradeRun:
    """The preparation and Task 26 steps on a replay, returning the run for inspection."""
    with world.factory(world.case) as sandbox:
        run = world.run(world.replay_target(diff), sandbox)
        prepare_tree(run)
        load_baseline(run)
        run_producer_new(run)
        take_snapshot(run)
        return run


def assert_absent(
    record: object, absence: GradeAbsence, caplog: pytest.LogCaptureFixture, fragment: str = ""
) -> None:
    assert isinstance(record, ImplementationGrade)
    assert record.absence is absence
    assert record.absence_class is AbsenceClass.HARNESS
    assert any(r.levelno == logging.ERROR and fragment in r.getMessage() for r in caplog.records), [
        r.getMessage() for r in caplog.records
    ]


def test_a_replay_with_no_reference_grade_raises_and_logs_error(
    tmp_path: Path, grading_repo: GradingRepo, caplog: pytest.LogCaptureFixture
) -> None:
    reviewed: list[str] = []

    def counting_review(tree: Path, base: str) -> ReviewOutcome:
        reviewed.append(base)
        return quiet_review(tree, base)

    world, diff = build(tmp_path, grading_repo, reviewer=counting_review)
    with caplog.at_level(logging.ERROR), pytest.raises(MissingReferenceGrade):
        grade_one(world.case, world.replay_target(diff), world.deps)
    assert any(r.levelno == logging.ERROR for r in caplog.records)
    assert reviewed == [], "the missing reference is found before any paid review runs"


def test_producer_new_selection_never_includes_a_start_id(
    tmp_path: Path, grading_repo: GradingRepo
) -> None:
    seen: list[SuiteSelection] = []
    world, diff = build(
        tmp_path,
        grading_repo,
        suites=recording_suite(seen),
        collect=lambda sandbox, case: (*START_IDS, "t.py::new1", "t.py::new2"),
    )
    seed_reference(world, START_IDS)
    run = checks(world, diff)
    assert [selection.node_ids for selection in seen] == [("t.py::new1", "t.py::new2")]
    assert (run.producer_new_passed, run.producer_new_failed) == (2, 0)


def test_a_producer_that_added_no_tests_never_calls_run_suite(
    tmp_path: Path, grading_repo: GradingRepo
) -> None:
    world, diff = build(tmp_path, grading_repo, collect=lambda sandbox, case: START_IDS)
    seed_reference(world, START_IDS)
    run = checks(world, diff)  # the default suite double fails the test if it is called
    assert (run.producer_new_passed, run.producer_new_failed) == (0, 0)
    assert not any(entry.startswith("suite") for entry in world.factory.log)


def test_failing_producer_new_tests_are_counted_and_do_not_stop_the_grade(
    tmp_path: Path, grading_repo: GradingRepo
) -> None:
    seen: list[SuiteSelection] = []
    world, diff = build(
        tmp_path,
        grading_repo,
        suites=recording_suite(seen, NodeOutcome.FAILED),
        collect=lambda sandbox, case: (*START_IDS, "t.py::new"),
    )
    seed_reference(world, START_IDS)
    run = checks(world, diff)
    assert (run.producer_new_passed, run.producer_new_failed) == (0, 1)
    assert run.snapshot is not None


def test_lint_and_type_totals_sum_per_file(tmp_path: Path, grading_repo: GradingRepo) -> None:
    def measure(tree: Path, case: BenchmarkCase, head: str) -> CodeSnapshot:
        snapshot = default_snapshot(tree, case, head)
        snapshot = edit_measurement(
            snapshot, SnapshotMetric.LINT_COUNT, per_file={"a.py": 3, "b.py": 4}
        )
        return edit_measurement(snapshot, SnapshotMetric.TYPE_ERRORS, per_file={"a.py": 1, "b.py": 5})

    world, diff = build(tmp_path, grading_repo, measure=measure, collect=lambda s, c: START_IDS)
    seed_reference(world, START_IDS)
    run = checks(world, diff)
    assert (run.lint_total, run.type_total) == (7, 6)
    assert world.store.snapshots.get(run.snapshot.sha256)  # type: ignore[union-attr]


def test_a_case_without_a_type_command_leaves_type_total_none(
    tmp_path: Path, grading_repo: GradingRepo
) -> None:
    world, diff = build(tmp_path, grading_repo, commands=(SUITE, LINT), collect=lambda s, c: START_IDS)
    seed_reference(world, START_IDS)
    run = checks(world, diff)
    assert run.lint_total == 4
    assert run.type_total is None


def test_an_absent_lint_measurement_gives_none_not_zero(
    tmp_path: Path, grading_repo: GradingRepo
) -> None:
    from squadron.metrology.snapshot_models import AbsenceReason

    def measure(tree: Path, case: BenchmarkCase, head: str) -> CodeSnapshot:
        return edit_measurement(
            default_snapshot(tree, case, head),
            SnapshotMetric.LINT_COUNT,
            tool=None,
            rule_set=None,
            per_file={},
            absent=AbsenceReason.TOOL_FAILED,
            absent_detail="ruff did not run",
        )

    world, diff = build(tmp_path, grading_repo, measure=measure, collect=lambda s, c: START_IDS)
    seed_reference(world, START_IDS)
    assert checks(world, diff).lint_total is None


def test_a_tool_that_does_not_match_the_command_is_check_tool_mismatch(
    tmp_path: Path, grading_repo: GradingRepo, caplog: pytest.LogCaptureFixture
) -> None:
    def measure(tree: Path, case: BenchmarkCase, head: str) -> CodeSnapshot:
        wrong = ToolIdentity(name="flake8", version="7", counting="per finding")
        return edit_measurement(
            default_snapshot(tree, case, head), SnapshotMetric.LINT_COUNT, tool=wrong
        )

    world, diff = build(tmp_path, grading_repo, measure=measure, collect=lambda s, c: START_IDS)
    seed_reference(world, START_IDS)
    with caplog.at_level(logging.ERROR):
        record = grade_one(world.case, world.replay_target(diff), world.deps)
    assert_absent(record, GradeAbsence.CHECK_TOOL_MISMATCH, caplog, "flake8")


def test_a_raising_measurer_is_snapshot_failed(
    tmp_path: Path, grading_repo: GradingRepo, caplog: pytest.LogCaptureFixture
) -> None:
    def measure(tree: Path, case: BenchmarkCase, head: str) -> CodeSnapshot:
        raise RuntimeError("ruff crashed")

    world, diff = build(tmp_path, grading_repo, measure=measure, collect=lambda s, c: START_IDS)
    seed_reference(world, START_IDS)
    with caplog.at_level(logging.ERROR):
        record = grade_one(world.case, world.replay_target(diff), world.deps)
    assert_absent(record, GradeAbsence.SNAPSHOT_FAILED, caplog, "ruff crashed")


def test_a_suite_run_error_is_suite_error(
    tmp_path: Path, grading_repo: GradingRepo, caplog: pytest.LogCaptureFixture
) -> None:
    def suite(selection: SuiteSelection) -> SuiteRun:
        raise SuiteRunError("pytest produced no report")

    world, diff = build(
        tmp_path, grading_repo, suites=suite, collect=lambda s, c: (*START_IDS, "t.py::new")
    )
    seed_reference(world, START_IDS)
    with caplog.at_level(logging.ERROR):
        record = grade_one(world.case, world.replay_target(diff), world.deps)
    assert_absent(record, GradeAbsence.SUITE_ERROR, caplog, "no report")


def test_a_suite_timeout_is_grader_timeout(
    tmp_path: Path, grading_repo: GradingRepo, caplog: pytest.LogCaptureFixture
) -> None:
    def suite(selection: SuiteSelection) -> SuiteRun:
        return SuiteRun(results=(), timed_out=True)

    world, diff = build(
        tmp_path, grading_repo, suites=suite, collect=lambda s, c: (*START_IDS, "t.py::new")
    )
    seed_reference(world, START_IDS)
    with caplog.at_level(logging.ERROR):
        record = grade_one(world.case, world.replay_target(diff), world.deps)
    assert_absent(record, GradeAbsence.GRADER_TIMEOUT, caplog, "time limit")


class TestRealMeasurer:
    """``make_snapshot_measurer`` over a fixture tree, with a scripted tool runner."""

    @pytest.fixture(autouse=True)
    def only_git_on_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import shutil

        git = shutil.which("git")
        assert git is not None
        bin_dir = tmp_path / "git-only-bin"
        bin_dir.mkdir()
        (bin_dir / "git").symlink_to(git)
        monkeypatch.setenv("PATH", str(bin_dir))

    def test_it_measures_the_tracked_files_for_the_cases_project(
        self, tmp_path: Path, grading_repo: GradingRepo
    ) -> None:
        world = make_world(tmp_path, grading_repo)
        measure = make_snapshot_measurer(default_registry(), FakeToolRunner())
        with world.factory(world.case) as sandbox:
            snapshot = measure(sandbox.tree, world.case, "d" * 40)
        assert snapshot.project_id == world.case.project_id
        assert snapshot.commit_sha == "d" * 40
        python = next(entry for entry in snapshot.languages if entry.language.value == "python")
        assert python.file_count == 2  # the two .py files tracked in the start tree
