"""findings-addressed gate policy — did the round address the prior findings?

The decision is layered: deterministic screens first (zero tokens), a judge
only over the residue the screens cannot settle, and a verdict *derived* from
the per-finding statuses rather than declared by the model.

``UNKNOWN`` here means exactly one thing: the check could not run and the
system stops. A state whose right action is knowable resolves to that action
(round 1 → annotated PASS, byte-identical round → FAIL) — never to UNKNOWN.

Split across modules to keep each within the file-size guideline: ``models``
(vocabulary), ``screens`` (the deterministic layer), ``parsing`` (the judge's
status lines), ``judge`` (transport), ``verification`` (claim checking and the
derivation rule), and ``policy`` (which sequences them).
"""

from __future__ import annotations

from squadron.pipeline.actions.findings_addressed.evidence import (
    GATE_EVIDENCE_DOC_TYPE,
    GATE_EVIDENCE_FILENAME_FORMAT,
    GateEvidence,
    render_gate_evidence,
    save_gate_evidence,
)
from squadron.pipeline.actions.findings_addressed.judge import (
    JUDGE_TEMPLATE_NAME,
    JudgeLegResult,
    judge_residue,
)
from squadron.pipeline.actions.findings_addressed.models import (
    CONCERN_PLUS_SEVERITIES,
    FindingOutcome,
    FindingRecord,
    FindingStatus,
    SettlingScreen,
    concern_plus,
    read_findings,
)
from squadron.pipeline.actions.findings_addressed.parsing import (
    JudgeStatus,
    is_parse_failure,
    parse_status_lines,
    statuses_to_outcomes,
)
from squadron.pipeline.actions.findings_addressed.policy import FindingsAddressedPolicy
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
from squadron.pipeline.actions.findings_addressed.verification import (
    derive_addressed_verdict,
    verify_outcomes,
)

__all__ = [
    "CONCERN_PLUS_SEVERITIES",
    "GATE_EVIDENCE_DOC_TYPE",
    "GATE_EVIDENCE_FILENAME_FORMAT",
    "JUDGE_TEMPLATE_NAME",
    "GateEvidence",
    "FindingOutcome",
    "FindingRecord",
    "FindingStatus",
    "FindingsAddressedPolicy",
    "JudgeLegResult",
    "JudgeStatus",
    "RoundDiff",
    "ScreenResult",
    "SettlingScreen",
    "compute_round_diff",
    "concern_plus",
    "derive_addressed_verdict",
    "is_parse_failure",
    "judge_residue",
    "parse_status_lines",
    "read_findings",
    "render_gate_evidence",
    "save_gate_evidence",
    "run_deterministic_screens",
    "statuses_to_outcomes",
    "verify_outcomes",
    "screen_byte_identical",
    "screen_exact_match",
    "screen_git_failure",
    "screen_no_prior_round",
]
