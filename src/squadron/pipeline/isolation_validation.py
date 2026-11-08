"""Strict-validation check for dispatch steps that declare ``allowed_tools: []`` (#299).

``tool_isolation_error`` refuses such a step at dispatch. This finds the same refusal from
the pipeline file alone, so ``sq run --validate --strict`` reports it before any step spends.
Only a step whose model is a literal alias is checked; a model that arrives through a
placeholder, a pool or ``--model`` is still caught at dispatch.
"""

from __future__ import annotations

from squadron.models.aliases import resolve_model_alias
from squadron.pipeline.actions.tool_support import DispatchRoute, tool_isolation_error
from squadron.pipeline.models import PipelineDefinition, StepConfig, ValidationError
from squadron.pipeline.steps import StepTypeName
from squadron.providers.base import ProfileName
from squadron.providers.loader import ensure_provider_loaded
from squadron.providers.profiles import get_profile
from squadron.providers.registry import get_provider


def no_tools_isolation_errors(definition: PipelineDefinition) -> list[ValidationError]:
    """One error per top-level dispatch step that cannot run without tools on its model."""
    return [
        error for step in definition.steps if (error := _step_error(step, definition.model)) is not None
    ]


def _step_error(step: StepConfig, pipeline_model: str | None) -> ValidationError | None:
    if step.step_type != StepTypeName.DISPATCH or step.config.get("allowed_tools") != []:
        return None
    alias = step.config.get("model", pipeline_model)
    if not isinstance(alias, str) or "{" in alias:
        return None
    model_id, alias_profile = resolve_model_alias(alias)
    profile_name = str(step.config.get("profile") or alias_profile or ProfileName.SDK)
    provider_name = get_profile(profile_name).provider
    ensure_provider_loaded(provider_name)
    message = tool_isolation_error(
        step_name=step.name,
        model=model_id,
        provider=provider_name,
        route=DispatchRoute.AGENT,
        capabilities=get_provider(provider_name).capabilities,
    )
    if message is None:
        return None
    return ValidationError(field="allowed_tools", message=message, action_type=step.step_type)
