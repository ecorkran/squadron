"""Real pytest in real sandboxes: classification of every failure kind, no synthetic JSONL."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from squadron.benchmark.adapter import (
    FailureKind,
    NodeOutcome,
    NodeResult,
    SandboxContext,
    SuiteSelection,
)
from squadron.benchmark.python_adapter import PythonBenchmarkAdapter
from squadron.benchmark.scrubbed_env import CredentialGrant, ScrubbedEnvironment
from squadron.core.process_runner import SubprocessRunner
from tests.benchmark.support import git_tree

pytestmark = pytest.mark.network

ADAPTER = PythonBenchmarkAdapter()
CLASSIFY = "tests/test_classify.py::"
COLLECT_FILE = "tests/test_collect_fails.py"


def build_context(fixture: str, base: Path, suite_timeout_s: float) -> SandboxContext:
    tree = git_tree(fixture, base)
    env = ScrubbedEnvironment(base / "root", "sb", CredentialGrant.none(), dict(os.environ))
    env.prepare()
    ctx = SandboxContext(tree, base / "out", env, SubprocessRunner(), 600, suite_timeout_s)
    ADAPTER.resolve_environment(ctx)
    return ctx


@pytest.fixture(scope="module")
def classify_ctx(tmp_path_factory: pytest.TempPathFactory) -> Iterator[SandboxContext]:
    yield build_context("classify_project", tmp_path_factory.mktemp("classify"), 300)


@pytest.fixture(scope="module")
def full_run(classify_ctx: SandboxContext) -> dict[str, NodeResult]:
    run = ADAPTER.run_suite(classify_ctx, SuiteSelection.all_tests())
    assert not run.timed_out
    return {result.node_id: result for result in run.results}


@pytest.mark.parametrize(
    ("name", "outcome", "kind"),
    [
        ("test_assertion", NodeOutcome.FAILED, FailureKind.ASSERTION_FAILURE),
        ("test_project_crash", NodeOutcome.FAILED, FailureKind.PROJECT_EXCEPTION),
        ("test_missing_import", NodeOutcome.FAILED, FailureKind.MISSING_SYMBOL),
        ("test_module_attribute_error", NodeOutcome.FAILED, FailureKind.MISSING_SYMBOL),
        ("test_mock_patch_missing_target", NodeOutcome.FAILED, FailureKind.MISSING_SYMBOL),
        ("test_exception_in_test_code", NodeOutcome.FAILED, FailureKind.OTHER_EXCEPTION),
        ("test_exception_in_helper", NodeOutcome.FAILED, FailureKind.OTHER_EXCEPTION),
        ("test_passes", NodeOutcome.PASSED, None),
        ("test_skipped", NodeOutcome.SKIPPED, None),
        ("test_expected_failure", NodeOutcome.XFAILED, None),
    ],
)
def test_each_kind_and_outcome(
    full_run: dict[str, NodeResult], name: str, outcome: NodeOutcome, kind: FailureKind | None
) -> None:
    result = full_run[f"{CLASSIFY}{name}"]
    assert (result.outcome, result.failure_kind) == (outcome, kind)


def test_collection_error_has_its_own_result(full_run: dict[str, NodeResult]) -> None:
    result = full_run[COLLECT_FILE]
    assert (result.outcome, result.failure_kind) == (NodeOutcome.ERROR, FailureKind.COLLECTION_ERROR)


def test_bracketed_parametrized_id_round_trips(
    classify_ctx: SandboxContext, full_run: dict[str, NodeResult]
) -> None:
    node_id = f"{CLASSIFY}test_bracketed_id[a[1]]"
    assert full_run[node_id].outcome is NodeOutcome.PASSED
    run = ADAPTER.run_suite(classify_ctx, SuiteSelection.nodes((node_id,)))
    assert [(r.node_id, r.outcome) for r in run.results] == [(node_id, NodeOutcome.PASSED)]


def test_nodes_selection_returns_exactly_those(classify_ctx: SandboxContext) -> None:
    ids = (f"{CLASSIFY}test_passes", f"{CLASSIFY}test_assertion")
    run = ADAPTER.run_suite(classify_ctx, SuiteSelection.nodes(ids))
    assert [r.node_id for r in run.results] == list(ids)


def test_requested_node_in_a_broken_file_takes_its_collection_error(
    classify_ctx: SandboxContext,
) -> None:
    node_id = f"{COLLECT_FILE}::test_never_collected"
    [result] = ADAPTER.run_suite(classify_ctx, SuiteSelection.nodes((node_id,))).results
    assert (result.outcome, result.failure_kind) == (NodeOutcome.ERROR, FailureKind.COLLECTION_ERROR)


def test_node_id_that_does_not_exist_is_a_collection_error(classify_ctx: SandboxContext) -> None:
    node_id = f"{CLASSIFY}test_no_such_test"
    [result] = ADAPTER.run_suite(classify_ctx, SuiteSelection.nodes((node_id,))).results
    assert (result.node_id, result.failure_kind) == (node_id, FailureKind.COLLECTION_ERROR)


def test_deselect_removes_nodes_from_an_all_tests_run(classify_ctx: SandboxContext) -> None:
    gone = f"{CLASSIFY}test_assertion"
    run = ADAPTER.run_suite(classify_ctx, SuiteSelection.all_tests(deselect=(gone,)))
    assert gone not in {r.node_id for r in run.results}
    assert f"{CLASSIFY}test_passes" in {r.node_id for r in run.results}


def test_a_hung_suite_times_out_with_the_node_not_run(tmp_path: Path) -> None:
    ctx = build_context("sleep_project", tmp_path, 3)
    node_id = "test_sleep.py::test_sleeps"
    run = ADAPTER.run_suite(ctx, SuiteSelection.nodes((node_id,)))
    assert run.timed_out
    assert [(r.node_id, r.outcome) for r in run.results] == [(node_id, NodeOutcome.NOT_RUN)]
