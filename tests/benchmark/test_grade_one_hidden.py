"""``grade_one``: the hidden run, suppressions and the grade record (slice 425 Task 28)."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import pytest

from squadron.benchmark.adapter import NodeOutcome, SuiteSelection
from squadron.benchmark.grade_one import grade_one
from squadron.benchmark.tree_reader import TreeReader
from squadron.metrology.benchmark_models import BenchmarkCase
from squadron.metrology.grade_models import MAX_LISTED_ITEMS
from squadron.metrology.grade_records import ImplementationGrade
from squadron.metrology.snapshot_models import CodeSnapshot
from tests.benchmark.grade_support import (
    LoggingAdapter,
    LoggingBudget,
    World,
    default_snapshot,
    passing_suite,
    replay_world,
)
from tests.benchmark.grading_fixtures import HIDDEN_IDS, GradingRepo, make_grading_case


def graded(world: World, diff: bytes) -> ImplementationGrade:
    record = grade_one(world.case, world.replay_target(diff), world.deps)
    assert isinstance(record, ImplementationGrade)
    return record


def test_the_hidden_run_is_the_last_step(tmp_path: Path, grading_repo: GradingRepo) -> None:
    log: list[str] = []

    def measure(tree: Path, case: BenchmarkCase, head: str) -> CodeSnapshot:
        log.append("snapshot")
        return default_snapshot(tree, case, head)

    world, diff = replay_world(
        tmp_path,
        grading_repo,
        measure=measure,
        budget=LoggingBudget(log),
        adapter=lambda: LoggingAdapter(log),
    )
    world.factory.log = log
    graded(world, diff)
    steps = [e for e in log if e not in ("budget_check", "budget_charge", "deps_changed")]
    assert steps == ["restore", "snapshot", "restore_tests", "suite:2", "inject", "suite:3"]


def test_the_hidden_results_and_the_injected_ids_reach_the_record(
    tmp_path: Path, grading_repo: GradingRepo
) -> None:
    seen: list[SuiteSelection] = []
    world, diff = replay_world(tmp_path, grading_repo, suites=passing_suite(seen))
    record = graded(world, diff)
    assert record.result is not None
    assert record.absence is None
    assert record.result.hidden_total == len(HIDDEN_IDS)
    assert record.result.hidden_passed == len(HIDDEN_IDS)
    assert record.result.passed
    assert set(seen[-1].node_ids or ()) == {
        injected.replace("test_parts", "test_sqhidden_test_parts") for injected in HIDDEN_IDS
    }


def test_a_failing_hidden_node_is_recorded_and_the_grade_does_not_pass(
    tmp_path: Path, grading_repo: GradingRepo
) -> None:
    failing = "tests/review/test_sqhidden_test_parts.py::TestWorstVerdict::test_fail_outranks_unknown"
    world, diff = replay_world(
        tmp_path, grading_repo, suites=passing_suite(outcomes={failing: NodeOutcome.FAILED})
    )
    record = graded(world, diff)
    assert record.result is not None
    assert record.result.hidden_passed == len(HIDDEN_IDS) - 1
    assert [node.node_id for node in record.result.hidden_failures] == [failing]
    assert not record.result.passed


def test_a_hidden_node_the_run_did_not_report_counts_as_not_run(
    tmp_path: Path, grading_repo: GradingRepo
) -> None:
    from squadron.benchmark.adapter import SuiteRun

    def silent(selection: SuiteSelection) -> SuiteRun:
        return SuiteRun(results=())

    world, diff = replay_world(tmp_path, grading_repo, suites=silent)
    record = graded(world, diff)
    assert record.result is not None
    assert record.result.hidden_passed == 0
    assert {n.outcome for n in record.result.hidden_failures} == {NodeOutcome.NOT_RUN}
    assert not record.result.passed


def test_an_empty_hidden_set_never_calls_run_suite_for_the_hidden_step(
    tmp_path: Path, grading_repo: GradingRepo
) -> None:
    seen: list[SuiteSelection] = []
    case = make_grading_case(grading_repo).model_copy(
        update={"hidden_tests": (), "hidden_fixtures": ()}
    )
    world, diff = replay_world(tmp_path, grading_repo, case=case, suites=passing_suite(seen))
    record = graded(world, diff)
    assert record.result is not None
    assert record.result.hidden_total == 0
    assert record.result.passed  # reduces to no regressions
    assert len(seen) == 1  # the regression run only (no producer-new, no hidden)


def test_suppressions_are_counted_from_the_diff(tmp_path: Path, grading_repo: GradingRepo) -> None:
    world, diff = replay_world(tmp_path, grading_repo, "producer_b")
    record = graded(world, diff)
    assert record.result is not None
    suppressions = record.result.suppressions
    assert (suppressions.noqa_source, suppressions.type_ignore_source) == (1, 1)
    assert (suppressions.noqa_test, suppressions.type_ignore_test) == (0, 0)


def test_the_id_map_sidecar_exists_and_its_hash_is_on_the_record(
    tmp_path: Path, grading_repo: GradingRepo
) -> None:
    world, diff = replay_world(tmp_path, grading_repo)
    record = graded(world, diff)
    assert record.result is not None
    pairs = json.loads(world.store.nodes.get(record.result.hidden_id_map_sha256))
    assert sorted(original for original, _ in pairs) == sorted(HIDDEN_IDS)


def test_fifty_one_test_edits_keep_fifty_names_and_count_fifty_one(
    tmp_path: Path, grading_repo: GradingRepo
) -> None:
    from squadron.benchmark.python_grading import PythonGradingAdapter

    names = tuple(f"tests/test_{i:02}.py" for i in range(MAX_LISTED_ITEMS + 1))

    class ManyEdits(PythonGradingAdapter):
        def test_side_edits(self, tree: Path, start: TreeReader) -> tuple[str, ...]:
            return names

        def restore_test_files(self, tree: Path, start: TreeReader, paths: Sequence[str]) -> None:
            return None

    world, diff = replay_world(tmp_path, grading_repo, adapter=ManyEdits)
    record = graded(world, diff)
    assert record.result is not None
    assert record.result.test_edits == names[:MAX_LISTED_ITEMS]
    assert record.result.test_edit_count == MAX_LISTED_ITEMS + 1


def test_the_record_is_written_once_with_cost_wall_time_and_environment(
    tmp_path: Path, grading_repo: GradingRepo
) -> None:
    world, diff = replay_world(tmp_path, grading_repo)
    record = graded(world, diff)
    stored = world.store.grades_for("bench-1")
    assert [grade for _, grade in stored] == [record]
    assert record.grading_cost_usd == pytest.approx(0.1)
    assert record.environment_digest == world.factory.identity.identity_digest
    assert record.absence is None
    assert record.absence_class is None
