"""Resolve the gate step's judge model, then delegate to the shared transport.

The transport itself lives in ``squadron.review.addressed.judge`` — it is
review-domain logic with no pipeline dependency. What stays here is exactly
what is loop-specific: reading the gate step's ``judge:`` block and the
resolver cascade off an ``ActionContext``.
"""

from __future__ import annotations

import logging

from squadron.pipeline.actions.findings_addressed.screens import RoundDiff
from squadron.pipeline.models import ActionContext
from squadron.pipeline.resolver import ModelResolutionError
from squadron.providers.base import ProfileName
from squadron.review.addressed.judge import (
    JUDGE_TEMPLATE_NAME,
    JudgeLegResult,
    judge_residue_core,
)
from squadron.review.addressed.models import FindingRecord
from squadron.review.templates import get_template, load_all_templates

_logger = logging.getLogger(__name__)

#: Config key of the gate step's optional ``judge:`` block.
JUDGE_BLOCK_PARAM = "judge"


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
    """Resolve model and profile from *context*, then run the shared transport.

    A model that cannot be resolved is a judge failure, which the derivation
    maps to UNKNOWN: fail-closed, never fail-open. The template lookup here is
    only for the resolver's fallback model — an unregistered template is
    reported by the transport, once.
    """
    if not residue:
        return JudgeLegResult()

    load_all_templates()
    template = get_template(JUDGE_TEMPLATE_NAME)

    try:
        model_id, profile_name = _resolve_model(
            context, template.model if template is not None else None
        )
    except ModelResolutionError:
        _logger.exception("findings-addressed: could not resolve a judge model; leg fails closed")
        return JudgeLegResult(failed=True, template=JUDGE_TEMPLATE_NAME)

    return await judge_residue_core(
        residue=residue,
        fresh_findings=fresh_findings,
        diff=diff,
        model_id=model_id,
        profile=profile_name,
        cwd=context.cwd,
    )
