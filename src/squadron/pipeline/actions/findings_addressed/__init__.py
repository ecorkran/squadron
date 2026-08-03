"""findings-addressed gate policy — did the round address the prior findings?

The decision is layered: deterministic screens first (zero tokens), a judge
only over the residue the screens cannot settle, and a verdict *derived* from
the per-finding statuses rather than declared by the model.

``UNKNOWN`` here means exactly one thing: the check could not run and the
system stops. A state whose right action is knowable resolves to that action
(round 1 → annotated PASS, byte-identical round → FAIL) — never to UNKNOWN.

This package holds only what the gate loop needs beyond the shared core:
``screens`` (screen 0, which needs an iteration number, and screen 2, which
needs a fresh review),
``evidence`` (the gate-evidence artifact), ``policy`` (which sequences them),
and ``judge`` (the ``ActionContext`` model resolution in front of the shared
transport). The vocabulary itself — statuses, finding records, judge-output
parsing, claim verification, the round-diff measurement, the screens that read
it alone, and the transport — live in
:mod:`squadron.review.addressed`, which the interactive ``sq review resolve``
path consumes as well.
"""

from __future__ import annotations

from squadron.pipeline.actions.findings_addressed.evidence import (
    GATE_EVIDENCE_DOC_TYPE,
    GATE_EVIDENCE_FILENAME_FORMAT,
    GateEvidence,
    render_gate_evidence,
    save_gate_evidence,
)
from squadron.pipeline.actions.findings_addressed.judge import judge_residue
from squadron.pipeline.actions.findings_addressed.policy import FindingsAddressedPolicy
from squadron.pipeline.actions.findings_addressed.screens import (
    compute_round_diff,
    run_deterministic_screens,
    screen_exact_match,
    screen_no_prior_round,
)

__all__ = [
    "GATE_EVIDENCE_DOC_TYPE",
    "GATE_EVIDENCE_FILENAME_FORMAT",
    "GateEvidence",
    "FindingsAddressedPolicy",
    "compute_round_diff",
    "judge_residue",
    "render_gate_evidence",
    "save_gate_evidence",
    "run_deterministic_screens",
    "screen_exact_match",
    "screen_no_prior_round",
]
