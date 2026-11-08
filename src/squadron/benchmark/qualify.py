"""Per-candidate fix-case qualification (slice 422 D9).

A short sequence over stage functions: the pre-sandbox stages in ``qualify_stages`` and, for
a candidate that survives them, ``deps.sandbox_stages`` (the sandbox pipeline). Each outcome is
stored as one ``FixQualification``.
"""

from __future__ import annotations

from squadron.benchmark.fairness import FAIRNESS_RULE_VERSION
from squadron.benchmark.fix_discovery import FixCandidate
from squadron.benchmark.qualify_stages import run_pre_sandbox_stages
from squadron.benchmark.qualify_types import QualifyDeps, QualifyResult
from squadron.metrology.benchmark_environment import EnvironmentIdentity
from squadron.metrology.benchmark_models import BenchmarkCase, FixQualification, QualificationOutcome
from squadron.metrology.benchmark_store import BenchmarkRecordStore


def qualify_candidate(candidate: FixCandidate, deps: QualifyDeps) -> QualifyResult:
    """Qualify one candidate and store the result; ``BuildHalted`` when the build cannot go on."""
    return run_pre_sandbox_stages(deps, candidate)


def qualification_for(
    case: BenchmarkCase, environment: EnvironmentIdentity, store: BenchmarkRecordStore
) -> FixQualification | None:
    """The stored result for ``case`` in ``environment``, or ``None`` when it must be redone.

    Matches on project, fix commit (the case's reference), environment digest and the current
    rule version. A ``harness_error`` is never an answer. A rejected record is returned: it is
    the reason a case no longer qualifies. When this returns ``None`` the caller runs
    ``qualify_candidate`` again, with the sandbox it already holds.
    """
    record = store.get_fix_qualification(
        case.project_id, case.reference_sha, environment.identity_digest
    )
    if (
        record is None
        or record.rule_version != FAIRNESS_RULE_VERSION
        or record.outcome is QualificationOutcome.HARNESS_ERROR
    ):
        return None
    return record
