"""Shared types and the one record-writing helper for fix-case qualification (slice 422 D9, D10).

``QualifyDeps`` is the single injected object the pipeline stages take (DIP): tests hand in
fakes for the host, store, runner and the sandbox stages.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from squadron.benchmark.adapter import SandboxContext
from squadron.benchmark.build_errors import BuildHalted
from squadron.benchmark.diff_classify import DiffClassification
from squadron.benchmark.fairness import FAIRNESS_RULE_VERSION, FixCaseAdapter
from squadron.benchmark.fix_discovery import DiscoveryRejection, FixCandidate
from squadron.benchmark.test_first import SuiteRunner
from squadron.codehost.protocol import CodeHost
from squadron.core.process_runner import ProcessRunner
from squadron.metrology.benchmark_environment import EnvironmentIdentity
from squadron.metrology.benchmark_models import (
    CandidateRejection,
    FixQualification,
    HiddenTestVerdict,
    QualificationOutcome,
    TestRejection,
)
from squadron.metrology.benchmark_store import BenchmarkRecordStore
from squadron.metrology.errors import MetrologyStoreError
from squadron.metrology.project_id import ProjectId

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class QualifyResult:
    """The record a candidate ended with, and whether it was reused from an earlier run."""

    record: FixQualification
    reused: bool = False


SandboxStages = Callable[[FixCandidate, DiffClassification, str, "QualifyDeps"], QualifyResult]


class QualifySandbox(Protocol):
    """What the sandbox stages use of a built sandbox (``BenchmarkSandbox`` satisfies it)."""

    @property
    def identity(self) -> EnvironmentIdentity: ...

    def context(self) -> SandboxContext: ...


#: Builds a sandbox at a commit; entering it installs the environment, leaving it removes the
#: sandbox (or keeps it, as the factory was configured).
SandboxFactory = Callable[[str], AbstractContextManager[QualifySandbox]]


@dataclass(frozen=True)
class QualifyDeps:
    repo_root: Path
    project_id: ProjectId
    host: CodeHost
    store: BenchmarkRecordStore
    runner: ProcessRunner
    adapter: FixCaseAdapter
    sandbox_stages: SandboxStages
    sandbox_factory: SandboxFactory
    suite_runner: SuiteRunner
    repeats: int
    git_timeout_seconds: float


def record_outcome(
    deps: QualifyDeps,
    candidate: FixCandidate,
    outcome: QualificationOutcome,
    *,
    issue_ref: str | None = None,
    rejection: CandidateRejection | None = None,
    detail: str = "",
    case_id: str | None = None,
    hidden_verdicts: tuple[HiddenTestVerdict, ...] = (),
    excluded_with_reasons: tuple[tuple[str, TestRejection], ...] = (),
    environment: EnvironmentIdentity | None = None,
) -> QualifyResult:
    """Write one ``FixQualification`` and return it; a store failure halts the build.

    A result that cannot be stored is lost, so ``MetrologyStoreError`` is logged at ERROR and
    raised as ``BuildHalted``. ``environment`` is ``None`` for every outcome before a sandbox.
    """
    return _new_record(
        deps,
        candidate.sha,
        candidate.parent_sha,
        issue_ref if issue_ref is not None else candidate.issue_ref,
        environment=environment,
        outcome=outcome,
        case_id=case_id,
        rejection=rejection,
        detail=detail,
        hidden_verdicts=hidden_verdicts,
        excluded_with_reasons=excluded_with_reasons,
    )


def record_discovery_rejection(deps: QualifyDeps, rejected: DiscoveryRejection) -> QualifyResult:
    """Store the rejection of a closing commit that never became a candidate."""
    return _new_record(
        deps,
        rejected.sha,
        rejected.parent_sha,
        rejected.issue_ref,
        outcome=QualificationOutcome.REJECTED,
        rejection=rejected.rejection,
        detail=rejected.detail,
    )


def _new_record(
    deps: QualifyDeps, commit_sha: str, parent_sha: str, issue_ref: str | None, **fields: Any
) -> QualifyResult:
    """Build and store one ``FixQualification``; the fields every outcome shares are set here."""
    record = FixQualification.model_validate(
        {
            "project_id": deps.project_id,
            "commit_sha": commit_sha,
            "parent_sha": parent_sha,
            "issue_ref": issue_ref,
            "rule_version": FAIRNESS_RULE_VERSION,
            "repeats": deps.repeats,
            "created_at": datetime.now(UTC),
            "environment": None,  # only outcomes reached inside a sandbox carry one
            **fields,
        }
    )
    return _store(deps, record)


def reusable_record(
    store: BenchmarkRecordStore,
    project_id: ProjectId,
    commit_sha: str,
    environment: EnvironmentIdentity,
    repeats: int,
) -> FixQualification | None:
    """The stored result for this commit in this environment, or ``None`` when it must be redone.

    The single reuse predicate: same project, fix commit, environment digest, current rule
    version and repeat count (the flakiness verdicts depend on it). A ``harness_error`` is never
    an answer; a rejected record is (it is the reason a case does not qualify). Store errors
    propagate as ``MetrologyStoreError``.
    """
    record = store.get_fix_qualification(project_id, commit_sha, environment.identity_digest)
    if (
        record is None
        or record.rule_version != FAIRNESS_RULE_VERSION
        or record.repeats != repeats
        or record.outcome is QualificationOutcome.HARNESS_ERROR
    ):
        return None
    return record


def _store(deps: QualifyDeps, record: FixQualification) -> QualifyResult:
    try:
        deps.store.write_fix_qualification(record)
    except MetrologyStoreError as exc:
        message = f"could not store the qualification of {record.commit_sha[:12]}: {exc}"
        _logger.exception(message)
        raise BuildHalted(message) from exc
    return QualifyResult(record)
