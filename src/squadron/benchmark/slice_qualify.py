"""Slice-case qualification: reuse, the pre-sandbox checks and the pipeline (slice 426 D4-D6).

``qualify_slice_candidate`` runs the checks that need only git first, so a candidate that
cannot be a case never costs a sandbox, then the sandbox stages in ``slice_qualify_run``. A
failure the harness cannot attribute to the slice is recorded as ``harness_error``, never as
a rejection that blames it.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from squadron.benchmark.adapter import EnvironmentResolutionError, SuiteRunError
from squadron.benchmark.build_errors import BuildHalted
from squadron.benchmark.fairness import CollectionFailed, HarnessFailure
from squadron.benchmark.scrubbed_env import MissingHarnessHomeError, MissingHarnessToolError
from squadron.benchmark.slice_discovery import SliceCandidate, has_code_change
from squadron.benchmark.slice_git import SliceHarnessError
from squadron.benchmark.slice_qualify_run import parse_source_ref, run_sandbox_stages
from squadron.benchmark.slice_qualify_types import (
    QualificationStore,
    ReusedRecord,
    SliceQualifyDeps,
    SliceQualifyResult,
    StageOutcome,
)
from squadron.benchmark.slice_task import TaskTextRejection, task_text_at
from squadron.metrology.benchmark_environment import EnvironmentIdentity
from squadron.metrology.benchmark_models import BenchmarkCase, QualificationOutcome, TestRejection
from squadron.metrology.errors import MetrologyStoreError
from squadron.metrology.slice_case_models import SliceCandidateRejection, SliceQualification
from squadron.metrology.slice_range_models import SliceLanding
from squadron.replay.history_free_sandbox import SandboxError

_logger = logging.getLogger(__name__)

#: Bumped whenever any check below changes; a record with another version is redone.
SLICE_RULE_VERSION = 1
UNKNOWN_SLICE_NAME = "(unknown at fork)"

#: Failures that say nothing about the slice: a git query, a sandbox, a collection or a suite
#: run that did not answer. Each is recorded as ``harness_error``.
_HARNESS_FAILURES = (
    SliceHarnessError,
    HarnessFailure,
    SuiteRunError,
    SandboxError,
    EnvironmentResolutionError,
    CollectionFailed,
    MissingHarnessHomeError,
    MissingHarnessToolError,
)


def can_skip(record: SliceQualification, digest: str | None, repeats: int) -> bool:
    """Whether a stored result answers a candidate without running anything.

    The rule version must match and the outcome must not be ``harness_error``. A pre-sandbox
    record (``start_environment is None``) needs no digest or repeat count, because its checks
    read only git at fixed shas; any other record needs the fork environment's digest and the
    repeat count to match (the flaky and always-failing exclusions depend on the count), as
    422's ``reusable_record`` does for fix cases.
    """
    if (
        record.rule_version != SLICE_RULE_VERSION
        or record.outcome is QualificationOutcome.HARNESS_ERROR
    ):
        return False
    if record.start_environment is None:
        return True
    return (
        digest is not None
        and record.start_environment.identity_digest == digest
        and record.repeats == repeats
    )


def slice_qualification_for(
    store: QualificationStore,
    case: BenchmarkCase,
    environment: EnvironmentIdentity,
    repeats: int,
) -> SliceQualification | None:
    """The stored result for ``case`` in ``environment``, when its key, rule version and
    repeat count match."""
    index, after_sha = parse_source_ref(case)
    record = store.get_slice_qualification(
        case.project_id, index, after_sha, environment.identity_digest
    )
    if record is None or not can_skip(record, environment.identity_digest, repeats):
        return None
    return record


def qualify_slice_candidate(candidate: SliceCandidate, deps: SliceQualifyDeps) -> SliceQualifyResult:
    """One candidate to one stored ``SliceQualification`` (and, when qualified, its case)."""
    earlier = _lookup(deps, candidate, None)
    if earlier is not None and can_skip(earlier, None, deps.repeats):
        return SliceQualifyResult(earlier, reused=True)
    slice_name = UNKNOWN_SLICE_NAME
    try:
        checked = task_text_at(
            candidate.landing.fork_sha,
            candidate.slice_index,
            deps.repo,
            deps.runner,
            deps.git_timeout_s,
        )
        if isinstance(checked, TaskTextRejection):
            return _stored_rejection(
                deps, candidate, UNKNOWN_SLICE_NAME, checked.rejection, checked.detail
            )
        slice_name = checked.slice_name
        if not has_code_change(
            candidate.landing.fork_sha,
            candidate.landing.tip_sha,
            deps.repo,
            deps.runner,
            deps.git_timeout_s,
        ):
            return _stored_rejection(
                deps,
                candidate,
                slice_name,
                SliceCandidateRejection.NO_CODE_CHANGE,
                "every path in fork..tip is bookkeeping the judge does not see",
            )
        staged = run_sandbox_stages(candidate, checked, deps, _keyed_lookup(deps, candidate))
    except _HARNESS_FAILURES as exc:
        _logger.exception("harness failure qualifying slice %d", candidate.slice_index)
        detail = exc.detail if isinstance(exc, HarnessFailure) else f"{type(exc).__name__}: {exc}"
        return _write_result(
            deps, candidate, slice_name, QualificationOutcome.HARNESS_ERROR, detail=detail
        )
    return _from_stage(deps, candidate, slice_name, staged)


def _keyed_lookup(
    deps: SliceQualifyDeps, candidate: SliceCandidate
) -> Callable[[str], SliceQualification | None]:
    """A lookup the sandbox stages call with the fork environment's digest."""

    def lookup(digest: str) -> SliceQualification | None:
        record = _lookup(deps, candidate, digest)
        return record if record is not None and can_skip(record, digest, deps.repeats) else None

    return lookup


def _from_stage(
    deps: SliceQualifyDeps,
    candidate: SliceCandidate,
    slice_name: str,
    staged: StageOutcome | ReusedRecord,
) -> SliceQualifyResult:
    if isinstance(staged, ReusedRecord):
        return SliceQualifyResult(staged.record, reused=True, kept_paths=staged.kept_paths)
    if staged.case is not None:
        _write_case(deps, staged.case)
    return _write_result(
        deps,
        candidate,
        slice_name,
        QualificationOutcome.QUALIFIED if staged.case is not None else QualificationOutcome.REJECTED,
        rejection=staged.rejection,
        detail=staged.detail,
        case=staged.case,
        start_environment=staged.start_environment,
        reference_environment=staged.reference_environment,
        excluded=staged.excluded_with_reasons,
        kept_paths=staged.kept_paths,
    )


def _stored_rejection(
    deps: SliceQualifyDeps,
    candidate: SliceCandidate,
    slice_name: str,
    rejection: SliceCandidateRejection,
    detail: str,
) -> SliceQualifyResult:
    return _write_result(
        deps, candidate, slice_name, QualificationOutcome.REJECTED, rejection=rejection, detail=detail
    )


def record_slice_outcome(
    deps: SliceQualifyDeps,
    index: int,
    landing: SliceLanding,
    slice_name: str,
    outcome: QualificationOutcome,
    *,
    rejection: SliceCandidateRejection | None = None,
    detail: str = "",
    case_id: str | None = None,
    start_environment: EnvironmentIdentity | None = None,
    reference_environment: EnvironmentIdentity | None = None,
    excluded: tuple[tuple[str, TestRejection], ...] = (),
) -> SliceQualification:
    """Build and store one ``SliceQualification``; a store failure halts the build.

    Also the way a discovery rejection or harness failure is recorded, so every slice index in
    the record ends with a stored result.
    """
    record = SliceQualification(
        project_id=deps.project_id,
        slice_index=index,
        slice_name=slice_name,
        landing_after_sha=landing.after_sha,
        fork_sha=landing.fork_sha,
        tip_sha=landing.tip_sha,
        rule_version=SLICE_RULE_VERSION,
        start_environment=start_environment,
        reference_environment=reference_environment,
        repeats=deps.repeats,
        outcome=outcome,
        case_id=case_id,
        rejection=rejection,
        detail=detail,
        excluded_with_reasons=excluded,
        created_at=deps.clock(),
    )
    try:
        deps.qualifications.write_slice_qualification(record)
    except MetrologyStoreError as exc:
        message = f"could not store the qualification of slice {index}: {exc}"
        _logger.exception(message)
        raise BuildHalted(message) from exc
    return record


def _write_result(
    deps: SliceQualifyDeps,
    candidate: SliceCandidate,
    slice_name: str,
    outcome: QualificationOutcome,
    *,
    case: BenchmarkCase | None = None,
    kept_paths: tuple[Path, ...] = (),
    **fields: Any,
) -> SliceQualifyResult:
    """Store one result for ``candidate`` and return it with the case and kept trees."""
    record = record_slice_outcome(
        deps,
        candidate.slice_index,
        candidate.landing,
        slice_name,
        outcome,
        case_id=None if case is None else case.case_id,
        **fields,
    )
    return SliceQualifyResult(record, case=case, kept_paths=kept_paths)


def _lookup(
    deps: SliceQualifyDeps, candidate: SliceCandidate, digest: str | None
) -> SliceQualification | None:
    """The stored result for the candidate's key; an unreadable store halts the build."""
    landing = candidate.landing
    try:
        return deps.qualifications.get_slice_qualification(
            deps.project_id, candidate.slice_index, landing.after_sha, digest
        )
    except MetrologyStoreError as exc:
        message = f"unreadable qualification record for slice {candidate.slice_index}: {exc}"
        _logger.exception(message)
        raise BuildHalted(message) from exc


def _write_case(deps: SliceQualifyDeps, case: BenchmarkCase) -> None:
    try:
        deps.cases.write_case(case)
    except MetrologyStoreError as exc:
        message = f"could not store case {case.case_id}: {exc}"
        _logger.exception(message)
        raise BuildHalted(message) from exc
