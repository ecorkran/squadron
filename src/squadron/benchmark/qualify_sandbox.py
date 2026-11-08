"""The sandbox qualification stages, through test-first (slice 422 D4, D5, D6, D9, D10).

``qualify_in_sandbox`` is what ``QualifyDeps.sandbox_stages`` holds. It builds one sandbox at
the parent, then runs the checks from cheapest to most expensive on what survived: collection
and the boundary at the parent, collection and the trace at the reference, test-first at
parent plus overlay. A rejection ends the candidate at once; a harness failure is a
``harness_error`` record, never a verdict on the candidate.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial

from squadron.benchmark.adapter import EnvironmentResolutionError, SandboxContext, SuiteRunError
from squadron.benchmark.build_errors import BuildHalted
from squadron.benchmark.diff_classify import DiffClassification
from squadron.benchmark.fairness import (
    FAIRNESS_RULE_VERSION,
    AllowedBoundary,
    BoundaryUndecidable,
    CollectedTests,
    CollectionFailed,
    FairnessVerdict,
    FixCaseAdapter,
    HarnessFailure,
)
from squadron.benchmark.file_states import FileState, FileStates
from squadron.benchmark.fix_discovery import FixCandidate
from squadron.benchmark.qualify_survivors import qualify_survivors
from squadron.benchmark.qualify_types import (
    QualifyDeps,
    QualifyResult,
    QualifySandbox,
    record_outcome,
)
from squadron.benchmark.scrubbed_env import MissingHarnessHomeError, MissingHarnessToolError
from squadron.benchmark.test_first import run_test_first
from squadron.benchmark.test_sets import TestSets, sort_tests
from squadron.core.process_runner import ProcessTimedOutError
from squadron.metrology.benchmark_environment import EnvironmentIdentity
from squadron.metrology.benchmark_models import (
    CandidateRejection,
    FixQualification,
    HiddenTestVerdict,
    HiddenTestVerdictKind,
    QualificationOutcome,
)
from squadron.metrology.errors import MetrologyStoreError
from squadron.replay.history_free_sandbox import SandboxError

_logger = logging.getLogger(__name__)

_HARNESS_ERRORS = (HarnessFailure, ProcessTimedOutError, SuiteRunError)


def qualify_in_sandbox(
    candidate: FixCandidate,
    classification: DiffClassification,
    task_text: str,
    deps: QualifyDeps,
) -> QualifyResult:
    """Stages 3 to 6 (and 7, in ``qualify_survivors``) in one sandbox at the parent commit."""
    try:
        with deps.sandbox_factory(candidate.parent_sha) as sandbox:
            return _qualify_in(sandbox, candidate, classification, task_text, deps)
    except EnvironmentResolutionError as exc:
        _logger.error("environment unresolved for %s: %s", candidate.sha[:12], exc)
        return record_outcome(
            deps,
            candidate,
            QualificationOutcome.REJECTED,
            rejection=CandidateRejection.ENVIRONMENT_UNRESOLVED,
            detail=f"{exc.reason.value}: {exc.detail}",
        )
    except (SandboxError, MissingHarnessHomeError, MissingHarnessToolError) as exc:
        _logger.exception("sandbox could not be built for %s", candidate.sha[:12])
        return record_outcome(
            deps, candidate, QualificationOutcome.HARNESS_ERROR, detail=f"sandbox: {exc}"
        )


def _reusable(
    deps: QualifyDeps, candidate: FixCandidate, environment: EnvironmentIdentity
) -> FixQualification | None:
    """An earlier record for this exact key and rule version, unless it was a harness error."""
    try:
        existing = deps.store.get_fix_qualification(
            deps.project_id, candidate.sha, environment.identity_digest
        )
    except MetrologyStoreError as exc:
        message = f"unreadable qualification record for {candidate.sha[:12]}: {exc}"
        _logger.exception(message)
        raise BuildHalted(message) from exc
    if (
        existing is not None
        and existing.rule_version == FAIRNESS_RULE_VERSION
        and existing.outcome is not QualificationOutcome.HARNESS_ERROR
    ):
        return existing
    return None


def _qualify_in(
    sandbox: QualifySandbox,
    candidate: FixCandidate,
    classification: DiffClassification,
    task_text: str,
    deps: QualifyDeps,
) -> QualifyResult:
    environment = sandbox.identity
    reused = _reusable(deps, candidate, environment)
    if reused is not None:
        return QualifyResult(reused, reused=True)
    try:
        return _run_stages(sandbox, candidate, classification, task_text, deps)
    except _HARNESS_ERRORS as exc:
        _logger.exception("harness failure qualifying %s", candidate.sha[:12])
        detail = exc.detail if isinstance(exc, HarnessFailure) else f"{type(exc).__name__}: {exc}"
        return record_outcome(
            deps,
            candidate,
            QualificationOutcome.HARNESS_ERROR,
            detail=detail,
            environment=environment,
        )


def _rejected(
    deps: QualifyDeps,
    candidate: FixCandidate,
    environment: EnvironmentIdentity,
    rejection: CandidateRejection,
    detail: str,
    hidden_verdicts: tuple[HiddenTestVerdict, ...] = (),
) -> QualifyResult:
    return record_outcome(
        deps,
        candidate,
        QualificationOutcome.REJECTED,
        rejection=rejection,
        detail=detail,
        environment=environment,
        hidden_verdicts=hidden_verdicts,
    )


def _verdicts(
    hidden: tuple[str, ...],
    traced: dict[str, FairnessVerdict] | None,
    first: dict[str, FairnessVerdict],
) -> tuple[HiddenTestVerdict, ...]:
    """One verdict per hidden candidate: the trace rejection if any, else the test-first result."""
    verdicts: list[HiddenTestVerdict] = []
    for node_id in hidden:
        verdict = (traced or {}).get(node_id)
        if verdict is None or verdict.rejection is None:
            verdict = first[node_id]
        kind = (
            HiddenTestVerdictKind.QUALIFIED
            if verdict.rejection is None
            else HiddenTestVerdictKind.REJECTED
        )
        verdicts.append(
            HiddenTestVerdict(
                node_id=node_id, kind=kind, rejection=verdict.rejection, detail=verdict.detail
            )
        )
    return tuple(verdicts)


@dataclass(frozen=True)
class _ParentFacts:
    collected: CollectedTests
    allowed: AllowedBoundary


Reject = Callable[..., QualifyResult]


def _parent_checks(
    ctx: SandboxContext, adapter: FixCaseAdapter, reject: Reject
) -> _ParentFacts | QualifyResult:
    """Stage 4: collection, then the packaging boundary, at the parent file state."""
    try:
        collected = adapter.collect(ctx)
    except CollectionFailed as exc:
        return reject(CandidateRejection.COLLECTION_FAILED, f"at the parent: {exc}")
    try:
        allowed = adapter.boundary(ctx)
    except BoundaryUndecidable as exc:
        return reject(CandidateRejection.BOUNDARY_UNDECIDABLE, str(exc))
    if not allowed.entries:
        return reject(
            CandidateRejection.NO_PACKAGING_BOUNDARY, "no script target and no top-level __all__"
        )
    return _ParentFacts(collected, allowed)


def _reference_checks(
    ctx: SandboxContext,
    adapter: FixCaseAdapter,
    states: FileStates,
    parent: _ParentFacts,
    reject: Reject,
) -> tuple[TestSets, dict[str, FairnessVerdict]] | QualifyResult:
    """Stage 5, still at the reference state: collect, sort, then trace the hidden candidates."""
    states.switch_to(ctx, adapter, FileState.REFERENCE)
    try:
        reference_collected = adapter.collect(ctx)
    except CollectionFailed as exc:
        return reject(CandidateRejection.COLLECTION_FAILED, f"at the reference: {exc}")
    sets = sort_tests(parent.collected, reference_collected)
    if not sets.hidden_candidates:
        return reject(CandidateRejection.NO_QUALIFYING_HIDDEN_TEST, "the fix adds or changes no test")
    return sets, dict(adapter.trace(ctx, sets.hidden_candidates, parent.allowed))


def _run_stages(
    sandbox: QualifySandbox,
    candidate: FixCandidate,
    classification: DiffClassification,
    task_text: str,
    deps: QualifyDeps,
) -> QualifyResult:
    ctx, adapter, environment = sandbox.context(), deps.adapter, sandbox.identity
    reject = partial(_rejected, deps, candidate, environment)
    parent = _parent_checks(ctx, adapter, reject)
    if isinstance(parent, QualifyResult):
        return parent
    states = FileStates.build(
        deps.runner,
        deps.repo_root,
        classification,
        candidate.parent_sha,
        candidate.sha,
        deps.git_timeout_seconds,
    )
    reference = _reference_checks(ctx, adapter, states, parent, reject)
    if isinstance(reference, QualifyResult):
        return reference
    sets, traced = reference
    survivors = tuple(node for node in sets.hidden_candidates if traced[node].rejection is None)
    first: dict[str, FairnessVerdict] = {}
    if survivors:
        states.switch_to(ctx, adapter, FileState.PARENT_PLUS_OVERLAY)
        first = run_test_first(deps.suite_runner, ctx, survivors, deps.repeats)
    verdicts = _verdicts(sets.hidden_candidates, traced, first)
    if not any(v.kind is HiddenTestVerdictKind.QUALIFIED for v in verdicts):
        return reject(
            CandidateRejection.NO_QUALIFYING_HIDDEN_TEST, "every hidden test was rejected", verdicts
        )
    return qualify_survivors(sandbox, candidate, task_text, sets, verdicts, states, deps)
