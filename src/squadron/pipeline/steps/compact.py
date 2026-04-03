"""Compact step type — translates compact config into a single compact action."""

from __future__ import annotations

from typing import cast

from squadron.pipeline.models import StepConfig, ValidationError
from squadron.pipeline.steps import StepTypeName, register_step_type


class CompactStepType:
    """Step type that expands to a single compact action."""

    @property
    def step_type(self) -> str:
        return StepTypeName.COMPACT

    def validate(self, config: StepConfig) -> list[ValidationError]:
        errors: list[ValidationError] = []
        cfg = config.config

        keep = cfg.get("keep")
        if keep is not None and (
            not isinstance(keep, list)
            or not all(isinstance(item, str) for item in cast(list[object], keep))
        ):
            errors.append(
                ValidationError(
                    field="keep",
                    message="'keep' must be a list of strings",
                    action_type=self.step_type,
                )
            )

        summarize = cfg.get("summarize")
        if summarize is not None and not isinstance(summarize, bool):
            errors.append(
                ValidationError(
                    field="summarize",
                    message="'summarize' must be a boolean",
                    action_type=self.step_type,
                )
            )

        return errors

    def expand(self, config: StepConfig) -> list[tuple[str, dict[str, object]]]:
        cfg = config.config
        action_config: dict[str, object] = {}

        if "keep" in cfg:
            action_config["keep"] = cfg["keep"]
        if "summarize" in cfg:
            action_config["summarize"] = cfg["summarize"]
        if "template" in cfg:
            action_config["template"] = cfg["template"]

        return [("compact", action_config)]


register_step_type(StepTypeName.COMPACT, CompactStepType())
