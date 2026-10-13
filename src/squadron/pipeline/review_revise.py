"""Compose a review-then-revise pipeline from a shipped pipeline's loop (slice 941).

``sq review <kind> --max N`` runs one review, then the revise loop that P4, P5 or P6
already carries. This module builds that two-step definition, ``[review, loop]``,
from the loaded pipeline so the loop YAML is never restated here (D1, D2).
"""

from __future__ import annotations

import copy
from typing import cast

from squadron.pipeline.loader import load_pipeline
from squadron.pipeline.loop_config import ExhaustBehavior
from squadron.pipeline.models import PipelineDefinition, StepConfig
from squadron.pipeline.steps import StepTypeName, unpack_inner_steps
from squadron.review.templates import BuiltinReviewTemplate

# Which shipped pipeline's loop revises which kind of artifact.
REVISE_PIPELINE_BY_KIND: dict[BuiltinReviewTemplate, str] = {
    BuiltinReviewTemplate.SLICE: "P4",
    BuiltinReviewTemplate.TASKS: "P5",
    BuiltinReviewTemplate.CODE: "P6",
}

REVIEW_STEP_NAME = "review"


def build_review_revise_definition(kind: BuiltinReviewTemplate) -> PipelineDefinition:
    """Return ``[review, loop]`` for *kind*, taken from its mapped pipeline.

    The loaded pipeline's steps are copied, never mutated. The loop's ``on_exhaust``
    becomes ``fail`` because ``checkpoint`` pauses for ``sq run --resume``, and no
    resumable state is written here (D4).

    Raises:
        ValueError: *kind* has no mapped pipeline, or the loaded pipeline's loop does
            not have the shape this composition relies on (D2). The message names
            the pipeline.
    """
    pipeline_name = REVISE_PIPELINE_BY_KIND.get(kind)
    if pipeline_name is None:
        raise ValueError(f"No revise pipeline is mapped for review kind '{kind}'")
    base = load_pipeline(pipeline_name)
    loop_step = _single_loop_step(base, pipeline_name)
    review_config = _body_review_config(loop_step, pipeline_name)
    loop_config = copy.deepcopy(loop_step.config)
    loop_config["on_exhaust"] = ExhaustBehavior.FAIL.value
    return PipelineDefinition(
        name=f"review-revise-{kind}",
        description=f"Review, then revise until the {kind} review passes (from {pipeline_name})",
        params=dict(base.params),
        steps=[
            StepConfig(
                step_type=StepTypeName.REVIEW,
                name=REVIEW_STEP_NAME,
                config=copy.deepcopy(review_config),
            ),
            StepConfig(
                step_type=StepTypeName.LOOP,
                name=loop_step.name,
                config=loop_config,
            ),
        ],
        model=base.model,
        auth_policy=base.auth_policy,
    )


def _single_loop_step(pipeline: PipelineDefinition, pipeline_name: str) -> StepConfig:
    loops = [step for step in pipeline.steps if step.step_type == StepTypeName.LOOP]
    if len(loops) != 1:
        raise ValueError(
            f"Pipeline '{pipeline_name}' must have exactly one loop step to revise with, "
            f"found {len(loops)}"
        )
    return loops[0]


def _body_review_config(loop_step: StepConfig, pipeline_name: str) -> dict[str, object]:
    """The loop body's single review step config, after checking the loop's shape (D2)."""
    raw_body = loop_step.config.get("steps", [])
    body = unpack_inner_steps(
        [cast(dict[str, object], s) for s in cast(list[object], raw_body) if isinstance(s, dict)]
    )
    reviews = [step for step in body if step.step_type == StepTypeName.REVIEW]
    if len(reviews) != 1:
        raise ValueError(
            f"Pipeline '{pipeline_name}': the loop body must have exactly one review step, "
            f"found {len(reviews)}"
        )
    if loop_step.config.get("until") is None:
        raise ValueError(f"Pipeline '{pipeline_name}': the loop must set 'until'")
    if loop_step.config.get("commit_each_iteration") is not True:
        raise ValueError(
            f"Pipeline '{pipeline_name}': the loop must set 'commit_each_iteration: true' "
            "so every round's revision is committed"
        )
    if loop_step.config.get("skip_if_met") is not True:
        raise ValueError(
            f"Pipeline '{pipeline_name}': the loop must set 'skip_if_met: true' "
            "so a passing first review runs zero rounds"
        )
    return reviews[0].config
