"""Edits are counted, not honored: real pytest in the grade tree (slice 425 Task 29, D4-D6).

The suite double runs the selected node ids with real pytest in the sandbox tree, so its
results depend only on the tree ``grade_one`` leaves it: the start commit's tool config and
the start commit's test files, plus the injected hidden module.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from squadron.benchmark.adapter import NodeOutcome, NodeResult, SuiteRun, SuiteSelection
from squadron.benchmark.grade_one import grade_one
from squadron.metrology.grade_records import ImplementationGrade
from tests.benchmark.grade_support import World, make_world, quiet_review, seed_reference
from tests.benchmark.grading_fixtures import (
    HIDDEN_FILE,
    GradingRepo,
    build_tree_with,
    build_variant,
    checkout_tree,
    collect_ids,
    make_grading_case,
    run_pytest_ids,
)

#: Hidden ids the reference fix reverses at the start commit: the fix supersedes them.
SUPERSEDED = (
    f"{HIDDEN_FILE}::TestWorstVerdict::test_every_ordered_pair[UNKNOWN-FAIL]",
    f"{HIDDEN_FILE}::TestWorstVerdict::test_every_ordered_pair[FAIL-UNKNOWN]",
)


def grade_diff(tmp_path: Path, repo: GradingRepo, diff: bytes) -> ImplementationGrade:
    start_tree = checkout_tree(repo, repo.start_sha, tmp_path / "start-tree")
    start_ids = collect_ids(start_tree, (HIDDEN_FILE,))
    case = make_grading_case(repo).model_copy(update={"superseded_tests": SUPERSEDED})
    holder: dict[str, World] = {}

    def suite(selection: SuiteSelection) -> SuiteRun:
        tree = holder["world"].factory.opened[-1].tree
        ids = selection.node_ids or ()
        outcomes = run_pytest_ids(tree, ids)
        return SuiteRun(
            results=tuple(NodeResult(i, NodeOutcome(outcomes.get(i, "not_run"))) for i in ids)
        )

    collect: Callable[..., tuple[str, ...]] = lambda sandbox, c: collect_ids(  # noqa: E731
        sandbox.tree, (HIDDEN_FILE,)
    )
    world = make_world(
        tmp_path / "world",
        repo,
        case=case,
        reviewer=quiet_review,
        suites=suite,
        collect=collect,
    )
    holder["world"] = world
    seed_reference(world, start_ids)
    record = grade_one(world.case, world.replay_target(diff), world.deps)
    assert isinstance(record, ImplementationGrade)
    return record


@pytest.fixture
def unedited(tmp_path: Path, grading_repo: GradingRepo) -> ImplementationGrade:
    """The same kind of replay with none of the edits: it adds an unrelated file."""
    diff = build_tree_with(
        grading_repo, "unedited", {"NOTES.md": "nothing to see\n"}, tmp_path / "unedited-producer"
    ).diff()
    record = grade_diff(tmp_path / "unedited-run", grading_repo, diff)
    assert record.result is not None
    assert record.result.passed
    return record


def assert_same_pass(record: ImplementationGrade, unedited: ImplementationGrade) -> None:
    assert record.result is not None and unedited.result is not None
    assert record.result.passed == unedited.result.passed
    assert record.result.hidden_passed == unedited.result.hidden_passed
    assert record.result.regression_failure_count == unedited.result.regression_failure_count


def test_edits_a_weakened_assertion_is_counted_and_the_pass_is_unchanged(
    tmp_path: Path, grading_repo: GradingRepo, unedited: ImplementationGrade
) -> None:
    diff = build_variant(grading_repo, "producer_a", tmp_path / "a").diff()
    record = grade_diff(tmp_path / "run-a", grading_repo, diff)
    assert record.result is not None
    assert record.result.test_edits == (HIDDEN_FILE,)
    assert record.result.test_edit_count == 1
    assert_same_pass(record, unedited)


def test_edits_added_suppressions_are_counted_and_the_pass_is_unchanged(
    tmp_path: Path, grading_repo: GradingRepo, unedited: ImplementationGrade
) -> None:
    diff = build_variant(grading_repo, "producer_b", tmp_path / "b").diff()
    record = grade_diff(tmp_path / "run-b", grading_repo, diff)
    assert record.result is not None
    suppressions = record.result.suppressions
    assert (suppressions.noqa_source, suppressions.type_ignore_source) == (1, 1)
    assert_same_pass(record, unedited)


def test_edits_a_loosened_tool_config_is_counted_and_the_pass_is_unchanged(
    tmp_path: Path, grading_repo: GradingRepo, unedited: ImplementationGrade
) -> None:
    diff = build_variant(grading_repo, "producer_c", tmp_path / "c").diff()
    record = grade_diff(tmp_path / "run-c", grading_repo, diff)
    assert record.result is not None
    assert record.result.config_edits == ("tool.pyright", "tool.ruff")
    assert record.result.config_edit_count == 2
    assert record.result.reinstalled  # the dependency and [tool.uv] changes
    assert_same_pass(record, unedited)


def test_edits_the_regression_run_sees_the_start_versions_of_edited_tests(
    tmp_path: Path, grading_repo: GradingRepo, unedited: ImplementationGrade
) -> None:
    """A producer that breaks every ordered-pair test would fail them if its file were run;
    the file is restored first, so the regression run is the start commit's."""
    start = grading_repo.start.read(HIDDEN_FILE).decode()
    broken = start.replace("worst_verdict([str(first), str(second)]) == expected", "False")
    assert broken != start
    diff = build_tree_with(
        grading_repo, "broken", {HIDDEN_FILE: broken}, tmp_path / "broken-producer"
    ).diff()
    record = grade_diff(tmp_path / "run-broken", grading_repo, diff)
    assert record.result is not None
    assert record.result.test_edits == (HIDDEN_FILE,)
    assert_same_pass(record, unedited)
