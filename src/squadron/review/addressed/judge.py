"""Consult a judge on the residue the deterministic screens could not settle.

Transport only: the call goes through ``run_review_with_profile`` and its
output is never persisted as a review file. Metrology's
``discover_judge_results`` globs ``*-review.*`` and keeps anything whose
template is a judge template, so a persisted file here would be swept into the
calibration sample set — decider evidence counted as assessor evidence.

Context-free by construction: the caller resolves the model and profile and
passes them in, so the same transport serves the gate loop
(``pipeline/actions/findings_addressed/judge.py``) and the interactive
``sq review resolve`` path without either owning the other's machinery.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from squadron.review.addressed.models import FindingOutcome, FindingRecord
from squadron.review.addressed.parsing import (
    is_parse_failure,
    parse_status_lines,
    statuses_to_outcomes,
)
from squadron.review.addressed.screens import RoundDiff
from squadron.review.review_client import run_review_with_profile
from squadron.review.templates import get_template, load_all_templates

_logger = logging.getLogger(__name__)

#: The bundled template this policy consults. Deliberately not a judge
#: template (no ``judge:`` block) — it emits statuses, not a score.
JUDGE_TEMPLATE_NAME = "judge.findings-addressed"


@dataclass(frozen=True)
class JudgeLegResult:
    """What the judge leg produced, and whether it could run at all."""

    outcomes: list[FindingOutcome] = field(default_factory=list[FindingOutcome])
    failed: bool = False
    model: str | None = None
    template: str | None = None


def _one_line(value: str) -> str:
    """Collapse *value* to a single line.

    Finding text is model-authored and reaches here through YAML, where a block
    scalar can carry newlines. One finding per line is a promise this function
    makes to the judge, so a field that spans lines would not merely look
    untidy — it would present as an extra finding, and a line shaped like a
    status would read as one.
    """
    return " ".join(value.split())


def _render_findings(records: list[FindingRecord]) -> str:
    """One finding per line, ids exactly as the judge must echo them back."""
    if not records:
        return "(none)"
    return "\n".join(
        f"- {record.finding_id}: [{_one_line(record.severity)}] "
        f"{_one_line(record.category)} at {_one_line(record.location)} "
        f"— {_one_line(record.summary)}"
        for record in records
    )


async def judge_residue_core(
    *,
    residue: list[FindingRecord],
    fresh_findings: list[FindingRecord],
    diff: RoundDiff,
    model_id: str | None,
    profile: str,
    cwd: str,
) -> JudgeLegResult:
    """Ask the judge for one status per residue finding.

    Invoked only when the residue is non-empty — round 1 and byte-identical
    rounds never reach here, which is what keeps the token cost proportional
    to genuine uncertainty. Any transport failure is a judge failure, which
    the derivation maps to UNKNOWN: fail-closed, never fail-open.
    """
    if not residue:
        return JudgeLegResult()

    load_all_templates()
    template = get_template(JUDGE_TEMPLATE_NAME)
    if template is None:
        _logger.error(
            "findings-addressed: judge template %r is not registered; leg fails closed",
            JUDGE_TEMPLATE_NAME,
        )
        return JudgeLegResult(failed=True, template=JUDGE_TEMPLATE_NAME)

    inputs = {
        "cwd": cwd,
        "prior_findings": _render_findings(residue),
        "round_diff": "\n".join(sorted(diff.changed_paths)) or "(no changed paths reported)",
        "fresh_findings": _render_findings(fresh_findings),
    }

    try:
        result = await run_review_with_profile(
            template,
            inputs,
            profile=profile,
            model=model_id,
        )
    except Exception:
        # Any transport failure is fail-closed: the gate reports UNKNOWN and a
        # human decides, rather than the round passing on an absent answer.
        _logger.exception(
            "findings-addressed: judge transport failed for %d residue finding(s)",
            len(residue),
        )
        return JudgeLegResult(failed=True, model=model_id, template=JUDGE_TEMPLATE_NAME)

    raw_output = result.raw_output or ""
    statuses = parse_status_lines(raw_output)
    if is_parse_failure(residue, statuses):
        _logger.warning(
            "findings-addressed: judge output carried no readable status line for any of "
            "%d residue finding(s); leg fails closed",
            len(residue),
        )
        return JudgeLegResult(failed=True, model=model_id, template=JUDGE_TEMPLATE_NAME)

    return JudgeLegResult(
        outcomes=statuses_to_outcomes(residue, statuses),
        model=model_id,
        template=JUDGE_TEMPLATE_NAME,
    )
