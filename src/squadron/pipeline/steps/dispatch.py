"""Dispatch step type — expands a dispatch config into a single dispatch action."""

from __future__ import annotations

from squadron.pipeline.models import StepConfig, ValidationError
from squadron.pipeline.steps import StepTypeName, register_step_type
from squadron.pipeline.steps.utils import validate_allowed_tools


class DispatchStepType:
    """Step type that expands to a single dispatch action.

    Accepts an optional ``prompt`` and optional ``model``. When ``prompt`` is
    absent the dispatch action falls back to the most recent ``build_context``
    output — the same behaviour as the dispatch action produced by phase steps.
    """

    @property
    def step_type(self) -> str:
        return StepTypeName.DISPATCH

    def validate(self, config: StepConfig) -> list[ValidationError]:
        errors: list[ValidationError] = []
        cfg = config.config

        prompt = cfg.get("prompt")
        if prompt is not None and not isinstance(prompt, str):
            errors.append(
                ValidationError(
                    field="prompt",
                    message="'prompt' must be a string",
                    action_type=self.step_type,
                )
            )

        model = cfg.get("model")
        if model is not None and not isinstance(model, str):
            errors.append(
                ValidationError(
                    field="model",
                    message="'model' must be a string",
                    action_type=self.step_type,
                )
            )

        fragment = cfg.get("pre_emption_fragment")
        if fragment is not None and not isinstance(fragment, str):
            errors.append(
                ValidationError(
                    field="pre_emption_fragment",
                    message="'pre_emption_fragment' must be a string",
                    action_type=self.step_type,
                )
            )

        errors.extend(validate_allowed_tools(config, self.step_type))

        return errors

    def expand(self, config: StepConfig) -> list[tuple[str, dict[str, object]]]:
        cfg = config.config
        action_config: dict[str, object] = {}

        # Only pass keys that are explicitly set — absent keys let the dispatch
        # action use its own resolution logic (e.g. prompt from build_context).
        if "prompt" in cfg:
            action_config["prompt"] = cfg["prompt"]
        if "model" in cfg:
            action_config["model"] = cfg["model"]
        if "pre_emption_fragment" in cfg:
            action_config["pre_emption_fragment"] = cfg["pre_emption_fragment"]
        if "allowed_tools" in cfg:
            action_config["allowed_tools"] = cfg["allowed_tools"]

        return [("dispatch", action_config)]


register_step_type(StepTypeName.DISPATCH, DispatchStepType())
