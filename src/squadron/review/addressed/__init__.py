"""Shared vocabulary of the findings-addressed derivation.

"Were the prior round's findings addressed?" is asked from two places: the
gate loop (``pipeline/actions/findings_addressed``) and the interactive
``sq review resolve`` path. What both need — the status vocabulary, how a
finding is read, how the judge's status lines parse, how a claim is verified
against a diff, and the transport that consults the judge — lives here, free
of any pipeline dependency, so neither entry point owns the other's machinery.

What stays in the pipeline package is exactly what is loop-specific: the
screens that need a fresh review, the gate-evidence artifact, and the policy
that plugs into the gate registry.
"""

from __future__ import annotations

from squadron.review.addressed.judge import (
    JUDGE_TEMPLATE_NAME,
    JudgeLegResult,
    judge_residue_core,
)
from squadron.review.addressed.models import (
    CONCERN_PLUS_SEVERITIES,
    FindingOutcome,
    FindingRecord,
    FindingStatus,
    SettlingScreen,
    concern_plus,
    read_findings,
    records_from_frontmatter,
)
from squadron.review.addressed.parsing import (
    JudgeStatus,
    is_parse_failure,
    parse_status_lines,
    statuses_to_outcomes,
)
from squadron.review.addressed.verification import (
    derive_addressed_verdict,
    verify_outcomes,
)

__all__ = [
    "CONCERN_PLUS_SEVERITIES",
    "JUDGE_TEMPLATE_NAME",
    "FindingOutcome",
    "FindingRecord",
    "FindingStatus",
    "JudgeLegResult",
    "JudgeStatus",
    "SettlingScreen",
    "concern_plus",
    "derive_addressed_verdict",
    "is_parse_failure",
    "judge_residue_core",
    "parse_status_lines",
    "read_findings",
    "records_from_frontmatter",
    "statuses_to_outcomes",
    "verify_outcomes",
]
