"""Stage 7: reference repeats, exclusions, case construction and ``qualification_for``."""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from squadron.benchmark.adapter import (
    FailureKind,
    NodeOutcome,
    NodeResult,
    SuiteRun,
    SuiteRunError,
)
from squadron.benchmark.build_errors import BuildHalted
from squadron.benchmark.fairness import (
    FAIRNESS_RULE_VERSION,
    CollectedTests,
    FairnessVerdict,
)
from squadron.benchmark.qualify import qualification_for
from squadron.benchmark.qualify_sandbox import qualify_in_sandbox
from squadron.benchmark.qualify_types import QualifyResult
from squadron.metrology.benchmark_models import (
    BenchmarkCase,
    CaseKind,
    CaseProvenance,
    ConftestFixture,
    GraderCommand,
    GraderCommandKind,
    HiddenTestVerdict,
    HiddenTestVerdictKind,
    QualificationOutcome,
    TestRejection,
)
from squadron.metrology.benchmark_store import BenchmarkRecordStore
from squadron.metrology.errors import MetrologyStoreError
from squadron.metrology.store import MetrologyStore
from tests.benchmark.test_qualify_sandbox import (
    CANDIDATE,
    CLASSIFICATION,
    FIX,
    HIDDEN_A,
    HIDDEN_B,
    PARENT,
    PROJECT,
    World,
    collected,
    environment,
    run,
    stored,
    world,
)

STABLE = "tests/test_old.py::stable"
FLAKY = "tests/test_old.py::flaky"
BROKEN = "tests/test_old.py::broken"
CHANGED = "tests/test_old.py::changed"
GONE = "tests/test_old.py::gone"
OLD = (STABLE, FLAKY, BROKEN)


def result(node: str, outcome: NodeOutcome) -> NodeResult:
    kind = FailureKind.ASSERTION_FAILURE if outcome is NodeOutcome.FAILED else None
    return NodeResult(node, outcome, kind)


def reference_run(**by_name: NodeOutcome) -> SuiteRun:
    """A full-suite run: ``stable``, ``flaky``, ``broken`` and the hidden tests, by short name."""
    nodes = {
        "stable": STABLE,
        "flaky": FLAKY,
        "broken": BROKEN,
        "a": HIDDEN_A,
        "b": HIDDEN_B,
        "changed": CHANGED,
    }
    return SuiteRun(results=tuple(result(nodes[name], outcome) for name, outcome in by_name.items()))


PASS, FAIL = NodeOutcome.PASSED, NodeOutcome.FAILED


def holds(*nodes: str) -> SuiteRun:
    """A test-first run where every named hidden test fails by assertion at the parent."""
    return SuiteRun(results=tuple(result(node, FAIL) for node in nodes))


def prepared(
    tmp_path: Path, *reference_runs: SuiteRun, hidden: tuple[str, ...] = (HIDDEN_A, HIDDEN_B)
) -> World:
    """A world whose test-first runs hold and whose reference runs are ``reference_runs``."""
    setup = world(tmp_path)
    setup.adapter.collections = [collected(*OLD), collected(*OLD, *hidden)]
    setup.adapter.traced = {node: FairnessVerdict(None) for node in hidden}
    setup.suites.script = [holds(*hidden)] * setup.deps.repeats + list(reference_runs)
    return setup


def collected_digests(digests: dict[str, str]) -> CollectedTests:
    return CollectedTests(digests=digests, fixtures_reached={}, conftest_fixtures=())


def verdict_for(outcome: QualifyResult, node: str) -> HiddenTestVerdict:
    return next(v for v in outcome.record.hidden_verdicts if v.node_id == node)


# --- The four exclusion and flakiness rules ------------------------------------------------


def test_a_hidden_test_that_differs_across_reference_runs_is_flaky(tmp_path: Path) -> None:
    setup = prepared(
        tmp_path,
        reference_run(stable=PASS, a=PASS, b=PASS),
        reference_run(stable=PASS, a=PASS, b=FAIL),
    )
    outcome = run(setup)
    assert outcome.record.outcome is QualificationOutcome.QUALIFIED
    flaky = verdict_for(outcome, HIDDEN_B)
    assert (flaky.kind, flaky.rejection) == (HiddenTestVerdictKind.REJECTED, TestRejection.FLAKY)
    assert flaky.detail == "reference runs: passed, failed"
    case = setup.store.get_case(outcome.record.case_id or "")
    assert case is not None and case.hidden_tests == (HIDDEN_A,)


def test_a_hidden_test_failing_every_reference_run_fails_at_reference(tmp_path: Path) -> None:
    setup = prepared(
        tmp_path,
        reference_run(stable=PASS, a=PASS, b=FAIL),
        reference_run(stable=PASS, a=PASS, b=FAIL),
    )
    outcome = run(setup)
    assert verdict_for(outcome, HIDDEN_B).rejection is TestRejection.FAILS_AT_REFERENCE
    assert verdict_for(outcome, HIDDEN_A).kind is HiddenTestVerdictKind.QUALIFIED


def test_a_non_hidden_test_that_differs_across_runs_is_excluded_as_flaky(tmp_path: Path) -> None:
    setup = prepared(
        tmp_path,
        reference_run(stable=PASS, flaky=PASS, a=PASS, b=PASS),
        reference_run(stable=PASS, flaky=FAIL, a=PASS, b=PASS),
    )
    outcome = run(setup)
    assert outcome.record.excluded_with_reasons == ((FLAKY, TestRejection.FLAKY),)
    case = setup.store.get_case(outcome.record.case_id or "")
    assert case is not None and case.excluded_tests == (FLAKY,)


def test_a_non_hidden_test_failing_every_run_is_excluded_as_failing_at_reference(
    tmp_path: Path,
) -> None:
    setup = prepared(
        tmp_path,
        reference_run(stable=PASS, broken=FAIL, a=PASS, b=PASS),
        reference_run(stable=PASS, broken=FAIL, a=PASS, b=PASS),
    )
    outcome = run(setup)
    assert outcome.record.excluded_with_reasons == ((BROKEN, TestRejection.FAILS_AT_REFERENCE),)


def test_superseded_tests_are_never_excluded_for_failing(tmp_path: Path) -> None:
    hidden = (HIDDEN_A, CHANGED)
    setup = prepared(
        tmp_path,
        reference_run(stable=PASS, a=PASS, changed=FAIL),
        reference_run(stable=PASS, a=PASS, changed=FAIL),
        hidden=hidden,
    )
    setup.adapter.collections = [
        collected_digests({**dict.fromkeys(OLD, "d"), CHANGED: "old", GONE: "d"}),
        collected_digests({**dict.fromkeys(OLD, "d"), CHANGED: "new", HIDDEN_A: "d"}),
    ]
    setup.suites.default[CHANGED] = result(CHANGED, FAIL)
    # Test-first runs once per file per repeat (the new file, then the old one).
    reference = reference_run(stable=PASS, a=PASS, changed=FAIL)
    setup.suites.script = [holds(HIDDEN_A), holds(CHANGED)] * 2 + [reference, reference]
    outcome = run(setup)
    assert outcome.record.excluded_with_reasons == ()
    case = setup.store.get_case(outcome.record.case_id or "")
    assert case is not None
    assert case.superseded_tests == (CHANGED, GONE)
    assert verdict_for(outcome, CHANGED).rejection is TestRejection.FAILS_AT_REFERENCE


def test_a_flaky_non_hidden_node_changes_the_case_id(tmp_path: Path) -> None:
    clean = run(
        prepared(
            tmp_path / "clean",
            reference_run(stable=PASS, flaky=PASS, a=PASS, b=PASS),
            reference_run(stable=PASS, flaky=PASS, a=PASS, b=PASS),
        )
    )
    flaky = run(
        prepared(
            tmp_path / "flaky",
            reference_run(stable=PASS, flaky=PASS, a=PASS, b=PASS),
            reference_run(stable=PASS, flaky=FAIL, a=PASS, b=PASS),
        )
    )
    assert clean.record.case_id is not None and flaky.record.case_id is not None
    assert clean.record.case_id != flaky.record.case_id


def test_one_fair_and_one_patching_hidden_test_qualifies_with_one(tmp_path: Path) -> None:
    setup = prepared(
        tmp_path,
        reference_run(stable=PASS, a=PASS),
        reference_run(stable=PASS, a=PASS),
    )
    setup.adapter.traced = {
        HIDDEN_A: FairnessVerdict(None),
        HIDDEN_B: FairnessVerdict(TestRejection.PATCHES_PROJECT_CODE, "pkg.mod.run"),
    }
    setup.suites.script = [holds(HIDDEN_A)] * 2 + [reference_run(stable=PASS, a=PASS)] * 2
    outcome = run(setup)
    assert outcome.record.outcome is QualificationOutcome.QUALIFIED
    case = setup.store.get_case(outcome.record.case_id or "")
    assert case is not None and case.hidden_tests == (HIDDEN_A,)
    reasons = {v.node_id: v.rejection for v in outcome.record.hidden_verdicts}
    assert reasons == {HIDDEN_A: None, HIDDEN_B: TestRejection.PATCHES_PROJECT_CODE}


def test_when_every_hidden_test_is_flaky_or_failing_the_candidate_is_rejected(tmp_path: Path) -> None:
    setup = prepared(
        tmp_path,
        reference_run(stable=PASS, a=PASS, b=FAIL),
        reference_run(stable=PASS, a=FAIL, b=FAIL),
    )
    outcome = run(setup)
    assert outcome.record.outcome is QualificationOutcome.REJECTED
    assert outcome.record.case_id is None
    assert [v.rejection for v in outcome.record.hidden_verdicts] == [
        TestRejection.FLAKY,
        TestRejection.FAILS_AT_REFERENCE,
    ]


def test_the_case_carries_the_candidates_content(tmp_path: Path) -> None:
    setup = prepared(
        tmp_path,
        reference_run(stable=PASS, a=PASS, b=PASS),
        reference_run(stable=PASS, a=PASS, b=PASS),
    )
    setup.adapter.grader_commands = lambda tree: (  # type: ignore[method-assign]
        GraderCommand(kind=GraderCommandKind.SUITE, argv=("python", "-m", "pytest")),
    )
    outcome = run(setup)
    case = setup.store.get_case(outcome.record.case_id or "")
    assert case is not None
    assert (case.start_sha, case.reference_sha, case.kind) == (PARENT, FIX, CaseKind.FIX)
    assert case.task_text == "task text"
    assert case.hidden_tests == (HIDDEN_A, HIDDEN_B)
    assert [c.kind for c in case.grader_commands] == [GraderCommandKind.SUITE]
    assert case.provenance.source_ref == "#5"
    assert outcome.record.environment == environment()
    assert setup.log[-2:] == ["suite", "overlay:parent"], "the tree is back at the parent state"


# --- qualification_for -----------------------------------------------------------------


def a_case() -> BenchmarkCase:
    return BenchmarkCase.build(
        project_id=PROJECT,
        kind=CaseKind.FIX,
        start_sha=PARENT,
        reference_sha=FIX,
        task_text="t",
        hidden_tests=(HIDDEN_A,),
        hidden_fixtures=(),
        superseded_tests=(),
        excluded_tests=(),
        grader_commands=(GraderCommand(kind=GraderCommandKind.SUITE, argv=("pytest",)),),
        provenance=CaseProvenance(source_ref="#5", created_at=datetime.now(UTC), built_by="test"),
    )


def test_qualification_for_returns_the_record_on_a_full_match(tmp_path: Path) -> None:
    setup = world(tmp_path)
    record = stored(setup)
    assert qualification_for(a_case(), environment(), setup.store, setup.deps.repeats) == record


@pytest.mark.parametrize(
    ("changes", "digest_env", "asked_repeats"),
    [
        ({"rule_version": FAIRNESS_RULE_VERSION + 1}, None, 2),
        ({}, "m" * 64, 2),
        ({"outcome": QualificationOutcome.HARNESS_ERROR, "case_id": None}, None, 2),
        ({}, None, 3),
    ],
    ids=["bumped rule version", "other environment", "harness error", "other repeat count"],
)
def test_qualification_for_returns_none_when_the_record_cannot_be_trusted(
    tmp_path: Path, changes: dict[str, object], digest_env: str | None, asked_repeats: int
) -> None:
    setup = world(tmp_path)
    stored(setup, **changes)
    asked = environment(digest_env) if digest_env else environment()
    assert qualification_for(a_case(), asked, setup.store, asked_repeats) is None


def test_qualification_for_returns_none_when_nothing_is_stored(tmp_path: Path) -> None:
    assert qualification_for(a_case(), environment(), world(tmp_path).store, 2) is None


# --- Failure modes -----------------------------------------------------------------------


def test_a_reference_suite_timeout_is_a_harness_error(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    setup = prepared(tmp_path, SuiteRun(results=(), timed_out=True))
    with caplog.at_level(logging.ERROR):
        outcome = run(setup)
    assert outcome.record.outcome is QualificationOutcome.HARNESS_ERROR
    assert "timed out" in outcome.record.detail
    assert any(record.levelno == logging.ERROR for record in caplog.records)


def test_a_suite_run_error_in_a_repeat_is_a_harness_error(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    setup = prepared(
        tmp_path, reference_run(stable=PASS, a=PASS, b=PASS), SuiteRunError("pytest exited 3: boom")
    )
    with caplog.at_level(logging.ERROR):
        outcome = run(setup)
    assert outcome.record.outcome is QualificationOutcome.HARNESS_ERROR
    assert "boom" in outcome.record.detail
    assert any(record.levelno == logging.ERROR for record in caplog.records)


class CaseWriteFails(BenchmarkRecordStore):
    def write_case(self, case: BenchmarkCase) -> str:
        raise MetrologyStoreError("disk full")


def test_a_failing_write_case_halts_the_build(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    setup = prepared(
        tmp_path,
        reference_run(stable=PASS, a=PASS, b=PASS),
        reference_run(stable=PASS, a=PASS, b=PASS),
    )
    failing_store = CaseWriteFails(MetrologyStore(store_dir=tmp_path / "store"))
    deps = replace(setup.deps, store=failing_store)
    with caplog.at_level(logging.ERROR), pytest.raises(BuildHalted, match="could not store case"):
        qualify_in_sandbox(CANDIDATE, CLASSIFICATION, "task text", deps)
    assert any(record.levelno == logging.ERROR for record in caplog.records)


def test_hidden_fixtures_are_those_reached_by_qualified_tests(tmp_path: Path) -> None:
    fixture = ConftestFixture(conftest_path="tests/conftest.py", fixture_name="extra")
    unused = ConftestFixture(conftest_path="tests/conftest.py", fixture_name="unused")
    setup = prepared(
        tmp_path,
        reference_run(stable=PASS, a=PASS),
        reference_run(stable=PASS, a=PASS),
    )
    setup.suites.script = [holds(HIDDEN_A)] * 2 + [reference_run(stable=PASS, a=PASS)] * 2
    setup.adapter.traced = {
        HIDDEN_A: FairnessVerdict(None),
        HIDDEN_B: FairnessVerdict(TestRejection.PATCHES_PROJECT_CODE, "x"),
    }
    reference = CollectedTests(
        digests=dict.fromkeys((*OLD, HIDDEN_A, HIDDEN_B), "digest"),
        fixtures_reached={HIDDEN_A: (fixture,), HIDDEN_B: (unused,)},
        conftest_fixtures=(fixture, unused),
    )
    setup.adapter.collections = [collected(*OLD), reference]
    outcome = run(setup)
    case = setup.store.get_case(outcome.record.case_id or "")
    assert case is not None and case.hidden_fixtures == (fixture,)
