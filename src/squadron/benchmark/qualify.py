"""Per-candidate fix-case qualification (slice 422 D9).

A short sequence over stage functions: the pre-sandbox stages in ``qualify_stages`` and, for
a candidate that survives them, ``deps.sandbox_stages`` (the sandbox pipeline). Each outcome is
stored as one ``FixQualification``.
"""

from __future__ import annotations

from squadron.benchmark.fix_discovery import FixCandidate
from squadron.benchmark.qualify_stages import run_pre_sandbox_stages
from squadron.benchmark.qualify_types import QualifyDeps, QualifyResult, reusable_record
from squadron.metrology.benchmark_environment import EnvironmentIdentity
from squadron.metrology.benchmark_models import BenchmarkCase, FixQualification
from squadron.metrology.benchmark_store import BenchmarkRecordStore


def qualify_candidate(candidate: FixCandidate, deps: QualifyDeps) -> QualifyResult:
    """Qualify one candidate and store the result; ``BuildHalted`` when the build cannot go on."""
    return run_pre_sandbox_stages(deps, candidate)


def qualification_for(
    case: BenchmarkCase,
    environment: EnvironmentIdentity,
    store: BenchmarkRecordStore,
    repeats: int,
) -> FixQualification | None:
    """The stored result for ``case`` in ``environment``, or ``None`` when it must be redone.

    Matches on the case's project and fix commit (its reference); see ``reusable_record`` for
    the rule. When this returns ``None`` the caller runs ``qualify_candidate`` again, which
    builds its own sandbox.
    """
    return reusable_record(store, case.project_id, case.reference_sha, environment, repeats)
