"""Consult a judge on the residue the deterministic screens could not settle.

Transport only: the call goes through ``run_review_with_profile`` and its
output is never persisted as a review file. Metrology's
``discover_judge_results`` globs ``*-review.*`` and keeps anything whose
template is a judge template, so a persisted file here would be swept into the
calibration sample set — decider evidence counted as assessor evidence.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from squadron.pipeline.actions.findings_addressed.screens import RoundDiff
from squadron.pipeline.models import ActionContext
from squadron.pipeline.resolver import ModelResolutionError
from squadron.providers.base import ProfileName
from squadron.review.addressed.models import FindingOutcome, FindingRecord
from squadron.review.addressed.parsing import (
    is_parse_failure,
    parse_status_lines,
    statuses_to_outcomes,
)
from squadron.review.review_client import run_review_with_profile
from squadron.review.templates import get_template, load_all_templates

_logger = logging.getLogger(__name__)

#: The bundled template this policy consults. Deliberately not a judge
#: template (no ``judge:`` block) — it emits statuses, not a score.
JUDGE_TEMPLATE_NAME = "judge.findings-addressed"

#: Config key of the gate step's optional ``judge:`` block.
JUDGE_BLOCK_PARAM = "judge"


@dataclass(frozen=True)
class JudgeLegResult:
    """What the judge leg produced, and whether it could run at all."""

    outcomes: list[FindingOutcome] = field(default_factory=list[FindingOutcome])
    failed: bool = False
    model: str | None = None
    template: str | None = None


def _render_findings(records: list[FindingRecord]) -> str:
    """One finding per line, ids exactly as the judge must echo them back."""
    if not records:
        return "(none)"
    return "\n".join(
        f"- {record.finding_id}: [{record.severity}] {record.category} at "
        f"{record.location} — {record.summary}"
        for record in records
    )


def _resolve_model(context: ActionContext, template_model: str | None) -> tuple[str | None, str]:
    """Resolve the judge's model and profile.

    The ``judge:`` block's ``model:`` wins when supplied; otherwise the
    standard resolver cascade, which lands on the pipeline's review tier — the
    judge never inherits the dispatch model.
    """
    judge_block = context.params.get(JUDGE_BLOCK_PARAM)
    block_model: str | None = None
    if isinstance(judge_block, dict):
        raw_model = judge_block.get("model")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        if isinstance(raw_model, str):
            block_model = raw_model

    step_model = str(context.params["step_model"]) if "step_model" in context.params else None
    try:
        model_id, alias_profile = context.resolver.resolve(block_model, step_model)
    except ModelResolutionError:
        if template_model is None:
            raise
        model_id, alias_profile = context.resolver.resolve(template_model, step_model)

    profile_name = (
        str(context.params["profile"])
        if "profile" in context.params
        else alias_profile or ProfileName.SDK
    )
    return model_id, profile_name


async def judge_residue(
    context: ActionContext,
    *,
    residue: list[FindingRecord],
    fresh_findings: list[FindingRecord],
    diff: RoundDiff,
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

    try:
        model_id, profile_name = _resolve_model(context, template.model)
    except ModelResolutionError:
        _logger.exception("findings-addressed: could not resolve a judge model; leg fails closed")
        return JudgeLegResult(failed=True, template=JUDGE_TEMPLATE_NAME)

    inputs = {
        "cwd": context.cwd,
        "prior_findings": _render_findings(residue),
        "round_diff": "\n".join(sorted(diff.changed_paths)) or "(no changed paths reported)",
        "fresh_findings": _render_findings(fresh_findings),
    }

    try:
        result = await run_review_with_profile(
            template,
            inputs,
            profile=profile_name,
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
