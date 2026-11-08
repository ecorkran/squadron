"""Per-candidate fix-case qualification (slice 422 D9).

A short sequence over stage functions: the pre-sandbox stages in ``qualify_stages`` and, for
a candidate that survives them, ``deps.sandbox_stages`` (the sandbox pipeline). Each outcome is
stored as one ``FixQualification``.
"""

from __future__ import annotations

from squadron.benchmark.fix_discovery import FixCandidate
from squadron.benchmark.qualify_stages import run_pre_sandbox_stages
from squadron.benchmark.qualify_types import QualifyDeps, QualifyResult


def qualify_candidate(candidate: FixCandidate, deps: QualifyDeps) -> QualifyResult:
    """Qualify one candidate and store the result; ``BuildHalted`` when the build cannot go on."""
    return run_pre_sandbox_stages(deps, candidate)
