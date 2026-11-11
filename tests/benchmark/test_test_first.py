"""The test-first check (slice 422 D5). ``network`` tests run in a real sandbox."""

from __future__ import annotations

import itertools
import logging
import os
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest

from squadron.benchmark.adapter import (
    FailureKind,
    NodeOutcome,
    NodeResult,
    SandboxContext,
    SuiteRun,
    SuiteRunError,
    SuiteSelection,
)
from squadron.benchmark.diff_classify import DiffClassification, classify_diff, parse_name_status
from squadron.benchmark.fairness import HarnessFailure
from squadron.benchmark.file_states import FileState, FileStates
from squadron.benchmark.python_adapter import PythonBenchmarkAdapter
from squadron.benchmark.python_fairness import PythonFixCaseAdapter
from squadron.benchmark.sandbox import BenchmarkSandbox
from squadron.benchmark.test_first import judge_parent_result, run_test_first
from squadron.core.process_runner import SubprocessRunner
from squadron.metrology.benchmark_models import TestRejection
from tests.benchmark.support import FixHistory, bare_context, fix_history, hermetic_git

NODE = "tests/test_a.py::t"


def result(outcome: NodeOutcome, kind: FailureKind | None = None) -> NodeResult:
    return NodeResult(NODE, outcome, kind)


def expected_verdict(outcome: NodeOutcome, kind: FailureKind | None) -> TestRejection | None:
    """D5 restated by hand, independently of the rule list under test."""
    if kind in (FailureKind.COLLECTION_ERROR, FailureKind.MISSING_SYMBOL):
        return TestRejection.USES_SYMBOL_ADDED_BY_FIX
    if outcome is NodeOutcome.ERROR:
        return TestRejection.UNDECIDABLE_FAILURE_AT_PARENT
    if outcome is NodeOutcome.PASSED:
        return TestRejection.PASSES_AT_PARENT
    if outcome is NodeOutcome.FAILED and kind in (
        FailureKind.ASSERTION_FAILURE,
        FailureKind.PROJECT_EXCEPTION,
    ):
        return None
    return TestRejection.UNDECIDABLE_FAILURE_AT_PARENT


def test_new_outcome_or_failure_kind_values_fail_until_the_rules_are_reviewed() -> None:
    assert {member.value for member in NodeOutcome} == {
        "passed",
        "failed",
        "error",
        "skipped",
        "xfailed",
        "xpassed",
        "not_run",
    }
    assert {member.value for member in FailureKind} == {
        "collection_error",
        "missing_symbol",
        "assertion_failure",
        "project_exception",
        "other_exception",
    }


@pytest.mark.parametrize(
    ("outcome", "kind"),
    list(itertools.product(NodeOutcome, [None, *FailureKind])),
    ids=lambda value: getattr(value, "value", "no-kind"),
)
def test_every_outcome_and_kind_pair_has_the_documented_verdict(
    outcome: NodeOutcome, kind: FailureKind | None
) -> None:
    assert judge_parent_result(result(outcome, kind)) == expected_verdict(outcome, kind)


@pytest.mark.parametrize(
    ("outcome", "kind", "verdict"),
    [
        (NodeOutcome.ERROR, FailureKind.COLLECTION_ERROR, TestRejection.USES_SYMBOL_ADDED_BY_FIX),
        (NodeOutcome.ERROR, FailureKind.MISSING_SYMBOL, TestRejection.USES_SYMBOL_ADDED_BY_FIX),
        (
            NodeOutcome.ERROR,
            FailureKind.ASSERTION_FAILURE,
            TestRejection.UNDECIDABLE_FAILURE_AT_PARENT,
        ),
        (NodeOutcome.FAILED, FailureKind.ASSERTION_FAILURE, None),
        (NodeOutcome.FAILED, FailureKind.PROJECT_EXCEPTION, None),
        (NodeOutcome.PASSED, None, TestRejection.PASSES_AT_PARENT),
        (
            NodeOutcome.FAILED,
            FailureKind.OTHER_EXCEPTION,
            TestRejection.UNDECIDABLE_FAILURE_AT_PARENT,
        ),
    ],
)
def test_the_named_rule_cases(
    outcome: NodeOutcome, kind: FailureKind | None, verdict: TestRejection | None
) -> None:
    assert judge_parent_result(result(outcome, kind)) == verdict


# --- run_test_first with scripted suites -----------------------------------------------


class ScriptedSuites:
    """Returns one scripted ``SuiteRun`` (or raises) per ``run_suite`` call."""

    def __init__(self, script: Sequence[SuiteRun | Exception]) -> None:
        self._script = list(script)
        self.calls = 0

    def run_suite(self, ctx: SandboxContext, selection: SuiteSelection) -> SuiteRun:
        self.calls += 1
        step = self._script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


def suite(outcome: NodeOutcome, kind: FailureKind | None = None) -> SuiteRun:
    return SuiteRun(results=(NodeResult(NODE, outcome, kind),))


CTX = bare_context(Path("."))
HOLDS = suite(NodeOutcome.FAILED, FailureKind.ASSERTION_FAILURE)
PASSES = suite(NodeOutcome.PASSED)


def test_a_consistent_node_gets_its_verdict_and_per_run_detail() -> None:
    runner = ScriptedSuites([HOLDS, HOLDS, HOLDS])
    verdicts = run_test_first(runner, CTX, [NODE], repeats=3)
    assert runner.calls == 3
    assert verdicts[NODE].rejection is None
    assert verdicts[NODE].detail == "runs: " + ", ".join(["failed/assertion_failure"] * 3)


def test_a_node_whose_verdict_differs_across_runs_is_flaky() -> None:
    verdicts = run_test_first(ScriptedSuites([HOLDS, PASSES, HOLDS]), CTX, [NODE], repeats=3)
    assert verdicts[NODE].rejection is TestRejection.FLAKY
    assert verdicts[NODE].detail == "runs: failed/assertion_failure, passed/-, failed/assertion_failure"


def test_consistently_undecidable_is_not_flaky() -> None:
    skipped = suite(NodeOutcome.SKIPPED)
    verdicts = run_test_first(ScriptedSuites([skipped, skipped]), CTX, [NODE], repeats=2)
    assert verdicts[NODE].rejection is TestRejection.UNDECIDABLE_FAILURE_AT_PARENT


def test_a_suite_timeout_is_a_harness_failure_with_an_error_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    timed_out = SuiteRun(results=(), timed_out=True)
    with caplog.at_level(logging.ERROR), pytest.raises(HarnessFailure, match="timed out") as caught:
        run_test_first(ScriptedSuites([timed_out]), CTX, [NODE], repeats=1)
    assert "timed out" in caught.value.detail
    assert any(record.levelno == logging.ERROR for record in caplog.records)


def test_a_suite_run_error_is_a_harness_failure_with_the_detail(
    caplog: pytest.LogCaptureFixture,
) -> None:
    runner = ScriptedSuites([SuiteRunError("pytest exited 3; stderr: boom")])
    with caplog.at_level(logging.ERROR), pytest.raises(HarnessFailure, match="boom"):
        run_test_first(runner, CTX, [NODE], repeats=2)
    assert runner.calls == 1, "the first failure stops the repeats"
    assert any(record.levelno == logging.ERROR for record in caplog.records)


# --- A real sandbox at parent plus overlay ----------------------------------------------

ADAPTER = PythonFixCaseAdapter()
RUNNER = SubprocessRunner()
ATTRIBUTE_NODE = "tests/test_symbol.py::test_uses_added_symbol"
IMPORT_NODE = "tests/test_symbol_import.py::test_imports_added_symbol"
BEHAVIOR_NODE = "tests/test_behavior.py::test_negative_is_clamped"


def classification_of(history: FixHistory) -> DiffClassification:
    raw = hermetic_git(
        history.repo, "diff", "--name-status", "--no-renames", history.parent_sha, history.fix_sha
    )
    parsed = classify_diff(
        parse_name_status(raw),
        ADAPTER,
        None,
        lambda path: hermetic_git(history.repo, "show", f"{history.parent_sha}:{path}"),
        lambda path: hermetic_git(history.repo, "show", f"{history.fix_sha}:{path}"),
    )
    assert isinstance(parsed, DiffClassification)
    return parsed


@pytest.fixture(scope="module")
def overlaid_context(tmp_path_factory: pytest.TempPathFactory) -> Iterator[SandboxContext]:
    history = fix_history("fixfair_project", "test_first", tmp_path_factory.mktemp("first"))
    sandbox = BenchmarkSandbox(
        start_sha=history.parent_sha,
        sandbox_id="first-parent",
        repo_root=history.repo,
        runner=RUNNER,
        adapter=PythonBenchmarkAdapter(),
        harness_env=dict(os.environ),
        install_timeout_s=900,
        suite_timeout_s=300,
        root=tmp_path_factory.mktemp("first_root"),
    )
    with sandbox:
        states = FileStates.build(
            RUNNER, history.repo, classification_of(history), history.parent_sha, history.fix_sha, 60
        )
        states.switch_to(sandbox.context(), ADAPTER, FileState.PARENT_PLUS_OVERLAY)
        yield sandbox.context()


@pytest.mark.network
def test_a_test_using_a_symbol_the_fix_added_is_rejected(overlaid_context: SandboxContext) -> None:
    verdicts = run_test_first(
        PythonBenchmarkAdapter(), overlaid_context, [ATTRIBUTE_NODE, IMPORT_NODE], repeats=2
    )
    assert verdicts[ATTRIBUTE_NODE].rejection is TestRejection.USES_SYMBOL_ADDED_BY_FIX
    assert verdicts[IMPORT_NODE].rejection is TestRejection.USES_SYMBOL_ADDED_BY_FIX
    assert "missing_symbol" in verdicts[ATTRIBUTE_NODE].detail
    assert "collection_error" in verdicts[IMPORT_NODE].detail


@pytest.mark.network
def test_a_test_that_fails_by_assertion_at_the_parent_holds(
    overlaid_context: SandboxContext,
) -> None:
    verdicts = run_test_first(PythonBenchmarkAdapter(), overlaid_context, [BEHAVIOR_NODE], repeats=2)
    assert verdicts[BEHAVIOR_NODE].rejection is None
    assert verdicts[BEHAVIOR_NODE].detail == "runs: failed/assertion_failure, failed/assertion_failure"


def test_each_test_file_runs_separately_in_every_repeat() -> None:
    selections: list[tuple[str, ...]] = []

    class Recording:
        def run_suite(self, ctx: SandboxContext, selection: SuiteSelection) -> SuiteRun:
            assert selection.node_ids is not None
            selections.append(selection.node_ids)
            return SuiteRun(
                results=tuple(NodeResult(n, NodeOutcome.PASSED) for n in selection.node_ids)
            )

    ids = ["tests/a.py::t1", "tests/b.py::t2", "tests/a.py::t3"]
    run_test_first(Recording(), CTX, ids, repeats=2)
    assert selections == [("tests/a.py::t1", "tests/a.py::t3"), ("tests/b.py::t2",)] * 2
