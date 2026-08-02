"""findings-addressed gate policy — did the round address the prior findings?

The decision is layered: deterministic screens first (zero tokens), a judge
only over the residue the screens cannot settle, and a verdict *derived* from
the per-finding statuses rather than declared by the model.

``UNKNOWN`` here means exactly one thing: the check could not run and the
system stops. A state whose right action is knowable resolves to that action
(round 1 → annotated PASS, byte-identical round → FAIL) — never to UNKNOWN.

Split across modules to keep each within the file-size guideline:
``models`` (vocabulary), ``screens`` (the deterministic layer).
"""

from __future__ import annotations

from squadron.pipeline.actions.findings_addressed.models import (
    CONCERN_PLUS_SEVERITIES,
    FindingOutcome,
    FindingRecord,
    FindingStatus,
    SettlingScreen,
    concern_plus,
    read_findings,
)
from squadron.pipeline.actions.findings_addressed.screens import (
    RoundDiff,
    ScreenResult,
    compute_round_diff,
    run_deterministic_screens,
    screen_byte_identical,
    screen_exact_match,
    screen_git_failure,
    screen_no_prior_round,
)

__all__ = [
    "CONCERN_PLUS_SEVERITIES",
    "FindingOutcome",
    "FindingRecord",
    "FindingStatus",
    "RoundDiff",
    "ScreenResult",
    "SettlingScreen",
    "compute_round_diff",
    "concern_plus",
    "read_findings",
    "run_deterministic_screens",
    "screen_byte_identical",
    "screen_exact_match",
    "screen_git_failure",
    "screen_no_prior_round",
]
