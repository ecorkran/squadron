"""Compact step type — translates compact config into a single compact action."""

from __future__ import annotations

from squadron.pipeline.models import StepConfig, ValidationError
from squadron.pipeline.steps import StepTypeName, register_step_type

_KNOWN_KEYS = frozenset({"model", "instructions"})


class CompactStepType:
    """Step type that expands to a single compact action."""

    @property
    def known_keys(self) -> frozenset[str]:
        return _KNOWN_KEYS

    @property
    def step_type(self) -> str:
        return StepTypeName.COMPACT

    def validate(self, config: StepConfig) -> list[ValidationError]:
        errors: list[ValidationError] = []
        cfg = config.config

        model = cfg.get("model")
        if model is not None and not isinstance(model, str):
            errors.append(
                ValidationError(
                    field="model",
                    message="'model' must be a string",
                    action_type=self.step_type,
                )
            )

        instructions = cfg.get("instructions")
        if instructions is not None and not isinstance(instructions, str):
            errors.append(
                ValidationError(
                    field="instructions",
                    message="'instructions' must be a string",
                    action_type=self.step_type,
                )
            )

        return errors

    def needs_context_forge(self, config: StepConfig) -> bool:
        """Compacts the SDK session; no Context Forge call."""
        return False

    def expand(self, config: StepConfig) -> list[tuple[str, dict[str, object]]]:
        cfg = config.config
        action_config: dict[str, object] = {}

        if "model" in cfg:
            action_config["model"] = cfg["model"]
        if "instructions" in cfg:
            action_config["instructions"] = cfg["instructions"]

        return [("compact", action_config)]


register_step_type(StepTypeName.COMPACT, CompactStepType())
