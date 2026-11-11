"""Stage 7: repeated reference runs, exclusions and case construction (slice 422 D8, D9).

Runs only for a candidate with at least one hidden test that survived the trace and the
test-first check. The full suite runs ``repeats`` times at the reference; the runs decide
which hidden tests are flaky or fail at the reference and which unchanged tests belong on the
case's exclusion list. Then the case is built and stored.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

from squadron.benchmark.adapter import NodeOutcome, NodeResult, SuiteSelection
from squadron.benchmark.build_errors import BuildHalted
from squadron.benchmark.file_states import FileState, FileStates
from squadron.benchmark.fix_discovery import FixCandidate
from squadron.benchmark.qualify_types import QualifyDeps, QualifyResult, QualifySandbox, record_outcome
from squadron.benchmark.test_first import run_selection
from squadron.benchmark.test_sets import TestSets
from squadron.metrology.benchmark_models import (
    BenchmarkCase,
    CandidateRejection,
    CaseKind,
    CaseProvenance,
    ConftestFixture,
    HiddenTestVerdict,
    HiddenTestVerdictKind,
    QualificationOutcome,
    TestRejection,
)
from squadron.metrology.errors import MetrologyStoreError

_logger = logging.getLogger(__name__)

BUILT_BY = "sq benchmark fix-cases build"
_FAILING = (NodeOutcome.FAILED, NodeOutcome.ERROR)

Runs = Sequence[Mapping[str, NodeResult]]


def _outcomes(runs: Runs, node_id: str) -> list[NodeOutcome]:
    """The node's outcome in each run; a node a run did not report counts as ``not_run``."""
    return [run[node_id].outcome if node_id in run else NodeOutcome.NOT_RUN for run in runs]


def _describe(outcomes: Sequence[NodeOutcome]) -> str:
    return "reference runs: " + ", ".join(outcome.value for outcome in outcomes)


def _hidden_rejection(outcomes: Sequence[NodeOutcome]) -> TestRejection | None:
    """A hidden test must pass at the reference in every run; disagreement is flakiness.

    Any outcome but ``passed`` (``skipped`` and ``not_run`` included) rejects it: a test that
    did not pass shows nothing about the fix. Regression tests follow the other half of the
    rule in ``_excluded_rejection``.
    """
    if len(set(outcomes)) > 1:
        return TestRejection.FLAKY
    if outcomes[0] is not NodeOutcome.PASSED:
        return TestRejection.FAILS_AT_REFERENCE
    return None


def _excluded_rejection(outcomes: Sequence[NodeOutcome]) -> TestRejection | None:
    """An unchanged test is excluded only when it fails (``failed``/``error``) or is flaky.

    The rule differs from ``_hidden_rejection`` on purpose: a hidden test must pass to be
    evidence, but a regression test only charges every configuration alike when it fails.
    ``skipped``, ``xfailed``, ``xpassed`` and ``not_run`` are not failures, so those tests stay.
    """
    if len(set(outcomes)) > 1:
        return TestRejection.FLAKY
    if outcomes[0] in _FAILING:
        return TestRejection.FAILS_AT_REFERENCE
    return None


def _apply_reference_runs(
    verdicts: tuple[HiddenTestVerdict, ...], runs: Runs
) -> tuple[HiddenTestVerdict, ...]:
    """Reject qualified hidden tests that are flaky or do not pass at the reference."""
    updated: list[HiddenTestVerdict] = []
    for verdict in verdicts:
        if verdict.kind is HiddenTestVerdictKind.QUALIFIED:
            outcomes = _outcomes(runs, verdict.node_id)
            rejection = _hidden_rejection(outcomes)
            if rejection is not None:
                verdict = HiddenTestVerdict(
                    node_id=verdict.node_id,
                    kind=HiddenTestVerdictKind.REJECTED,
                    rejection=rejection,
                    detail=_describe(outcomes),
                )
        updated.append(verdict)
    return tuple(updated)


def _excluded(unchanged: Sequence[str], runs: Runs) -> tuple[tuple[str, TestRejection], ...]:
    """Unchanged tests that are flaky or fail at the reference: they charge every config alike.

    Superseded tests are never excluded for failing: they leave the regression set anyway.
    """
    found: list[tuple[str, TestRejection]] = []
    for node_id in unchanged:
        rejection = _excluded_rejection(_outcomes(runs, node_id))
        if rejection is not None:
            found.append((node_id, rejection))
    return tuple(sorted(found))


def _hidden_fixtures(sets: TestSets, qualified: Sequence[str]) -> tuple[ConftestFixture, ...]:
    """Added conftest fixtures that a qualified hidden test reaches, deduplicated and sorted."""
    reached = {
        (fixture.conftest_path, fixture.fixture_name): fixture
        for node_id in qualified
        for fixture in sets.fixtures_by_hidden.get(node_id, ())
    }
    return tuple(reached[key] for key in sorted(reached))


def qualify_survivors(
    sandbox: QualifySandbox,
    candidate: FixCandidate,
    task_text: str,
    sets: TestSets,
    verdicts: tuple[HiddenTestVerdict, ...],
    states: FileStates,
    deps: QualifyDeps,
) -> QualifyResult:
    """Run the reference repeats, then store the case or the rejection that remains."""
    ctx, adapter, environment = sandbox.context(), deps.adapter, sandbox.identity
    states.switch_to(ctx, adapter, FileState.REFERENCE)
    runs = [
        run_selection(deps.suite_runner, ctx, SuiteSelection.all_tests()) for _ in range(deps.repeats)
    ]
    verdicts = _apply_reference_runs(verdicts, runs)
    excluded = _excluded(sets.unchanged, runs)
    qualified = tuple(v.node_id for v in verdicts if v.kind is HiddenTestVerdictKind.QUALIFIED)
    if not qualified:
        return record_outcome(
            deps,
            candidate,
            QualificationOutcome.REJECTED,
            rejection=CandidateRejection.NO_QUALIFYING_HIDDEN_TEST,
            detail="no hidden test survived the reference runs",
            hidden_verdicts=verdicts,
            excluded_with_reasons=excluded,
            environment=environment,
        )
    # Grader commands describe the parent's configuration, so read them at the parent state.
    states.switch_to(ctx, adapter, FileState.PARENT)
    case = BenchmarkCase.build(
        project_id=deps.project_id,
        kind=CaseKind.FIX,
        start_sha=candidate.parent_sha,
        reference_sha=candidate.sha,
        task_text=task_text,
        hidden_tests=qualified,
        hidden_fixtures=_hidden_fixtures(sets, qualified),
        superseded_tests=sets.superseded,
        excluded_tests=tuple(node_id for node_id, _ in excluded),
        grader_commands=adapter.grader_commands(ctx.tree),
        provenance=CaseProvenance(
            source_ref=candidate.issue_ref, created_at=datetime.now(UTC), built_by=BUILT_BY
        ),
    )
    try:
        deps.store.write_case(case)
    except MetrologyStoreError as exc:
        message = f"could not store case {case.case_id}: {exc}"
        _logger.exception(message)
        raise BuildHalted(message) from exc
    return record_outcome(
        deps,
        candidate,
        QualificationOutcome.QUALIFIED,
        case_id=case.case_id,
        hidden_verdicts=verdicts,
        excluded_with_reasons=excluded,
        environment=environment,
    )
