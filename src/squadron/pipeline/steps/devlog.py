"""Devlog step type — single devlog action with mode support."""

from __future__ import annotations

from squadron.pipeline.models import StepConfig, ValidationError
from squadron.pipeline.steps import StepTypeName, register_step_type

_VALID_MODES = ("auto", "explicit")


class DevlogStepType:
    """Step type that expands to a single devlog action."""

    @property
    def step_type(self) -> str:
        return StepTypeName.DEVLOG

    def validate(self, config: StepConfig) -> list[ValidationError]:
        errors: list[ValidationError] = []
        cfg = config.config

        mode = cfg.get("mode")
        if mode is not None and mode not in _VALID_MODES:
            errors.append(
                ValidationError(
                    field="mode",
                    message=f"'mode' must be one of {list(_VALID_MODES)}",
                    action_type=self.step_type,
                )
            )

        if mode == "explicit" and "content" not in cfg:
            errors.append(
                ValidationError(
                    field="content",
                    message="'content' is required when mode is 'explicit'",
                    action_type=self.step_type,
                )
            )

        return errors

    def expand(self, config: StepConfig) -> list[tuple[str, dict[str, object]]]:
        cfg = config.config

        action_config: dict[str, object] = {
            "mode": cfg.get("mode", "auto"),
        }

        if "content" in cfg:
            action_config["content"] = cfg["content"]

        return [("devlog", action_config)]


register_step_type(StepTypeName.DEVLOG, DevlogStepType())
