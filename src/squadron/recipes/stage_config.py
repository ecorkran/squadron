"""Resolved alias settings to 430's ``StageConfig`` (slice 434, D8).

``config_key`` covers model, profile, template hash, ``tool_use`` and
``max_output_tokens``. A recipe review's review stages use the step's own template hash;
comb stages use the built-in ``comb`` template's. ``sq benchmark recall`` builds its live
stage identity through ``stage_config`` too, so both sides key stages the same way.
"""

from __future__ import annotations

from dataclasses import dataclass

from squadron.data import data_dir
from squadron.metrology.identity import template_behavior_hash
from squadron.metrology.recall_run_models import StageConfig, StageKind
from squadron.models.aliases import (
    model_allows_tools,
    model_effort,
    model_max_output_tokens,
    resolve_model_alias,
)
from squadron.recipes.comb_call import StageModel
from squadron.recipes.recipe import Recipe, RequiredStage, required_stages
from squadron.review.templates import ReviewTemplate, load_template

#: The built-in template every comb stage sends.
COMB_TEMPLATE_NAME = "comb"
_TEMPLATES_SUBDIR = "templates"
_TEMPLATE_SUFFIX = ".yaml"


class StageConfigError(ValueError):
    """An alias or template that gives no stage identity."""


def builtin_template(name: str) -> ReviewTemplate:
    """The shipped template file, never a user override: its hash is the stage identity."""
    path = data_dir() / _TEMPLATES_SUBDIR / f"{name}{_TEMPLATE_SUFFIX}"
    if not path.is_file():
        raise StageConfigError(f"built-in template {name!r} not found at {path}")
    return load_template(path)


def builtin_template_hash(name: str) -> str:
    """The behavior hash of the shipped template *name*."""
    return template_behavior_hash(builtin_template(name))


def stage_config(alias: str, model: str, profile: str, template_hash: str) -> StageConfig:
    """The stage identity of *alias* sent as *model* on *profile* with that template."""
    return StageConfig(
        model=model,
        profile=profile,
        template_hash=template_hash,
        tool_use=model_allows_tools(alias),
        max_output_tokens=model_max_output_tokens(alias),
    )


def alias_stage_config(alias: str, template_hash: str) -> StageConfig:
    """Production entry: model and profile from the alias registry; no profile raises."""
    resolved = stage_model(alias)
    return stage_config(alias, resolved.model, resolved.profile, template_hash)


def stage_model(alias: str) -> StageModel:
    """What a stage call is sent with, from the alias registry; no profile raises."""
    model, profile = resolve_model_alias(alias)
    if profile is None:
        raise StageConfigError(f"model alias {alias!r} is unknown or has no provider profile")
    return StageModel(
        alias=alias,
        model=model,
        profile=profile,
        effort=model_effort(alias),
        max_output_tokens=model_max_output_tokens(alias),
        allows_tools=model_allows_tools(alias),
    )


def stage_alias(stage: RequiredStage) -> str:
    """The alias a required stage calls: the reviewer, or the last comb of its chain."""
    return stage.chain[-1] if stage.kind is StageKind.COMB else stage.reviewer


def planned_stages(recipe: Recipe, review_template_hash: str) -> list[StageConfig]:
    """One config per ``required_stages`` entry, in order, resolved before any call."""
    comb_hash = builtin_template_hash(COMB_TEMPLATE_NAME)
    return [
        alias_stage_config(
            stage_alias(stage),
            comb_hash if stage.kind is StageKind.COMB else review_template_hash,
        )
        for stage in required_stages(recipe)
    ]


@dataclass(frozen=True)
class RecipePlan:
    """What a recipe review resolves before its first call: every stage's config, what each
    member alias is sent with, and the comb template. Built off the event loop (alias,
    template and YAML file reads)."""

    planned: tuple[StageConfig, ...]
    models: dict[str, StageModel]
    comb_template: ReviewTemplate


def plan_recipe(recipe: Recipe, review_template: ReviewTemplate) -> RecipePlan:
    """The plan for *recipe* run in place of *review_template*'s single model."""
    return RecipePlan(
        planned=tuple(planned_stages(recipe, template_behavior_hash(review_template))),
        models={alias: stage_model(alias) for alias in (*recipe.reviewers, *recipe.combs)},
        comb_template=builtin_template(COMB_TEMPLATE_NAME),
    )
