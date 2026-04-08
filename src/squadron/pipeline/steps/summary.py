"""Summary step type — generates a summary and emits it to one or more destinations."""

from __future__ import annotations

from squadron.pipeline.actions.checkpoint import CheckpointTrigger
from squadron.pipeline.emit import parse_emit_list
from squadron.pipeline.models import StepConfig, ValidationError
from squadron.pipeline.steps import StepTypeName, register_step_type


class SummaryStepType:
    """Step type: expands to a summary action, optionally followed by a checkpoint."""

    @property
    def step_type(self) -> str:
        return StepTypeName.SUMMARY

    def validate(self, config: StepConfig) -> list[ValidationError]:
        errors: list[ValidationError] = []
        cfg = config.config

        template = cfg.get("template")
        if template is not None and not isinstance(template, str):
            errors.append(
                ValidationError(
                    field="template",
                    message="'template' must be a string",
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

        emit_raw = cfg.get("emit")
        if emit_raw is not None:
            try:
                parse_emit_list(emit_raw)
            except ValueError as exc:
                errors.append(
                    ValidationError(
                        field="emit",
                        message=str(exc),
                        action_type=self.step_type,
                    )
                )

        checkpoint = cfg.get("checkpoint")
        if checkpoint is not None:
            valid_triggers = [t.value for t in CheckpointTrigger]
            if checkpoint not in valid_triggers:
                errors.append(
                    ValidationError(
                        field="checkpoint",
                        message=(
                            f"'{checkpoint}' is not a valid checkpoint trigger. "
                            f"Valid values: {valid_triggers}"
                        ),
                        action_type=self.step_type,
                    )
                )

        return errors

    def expand(self, config: StepConfig) -> list[tuple[str, dict[str, object]]]:
        cfg = config.config
        summary_config: dict[str, object] = {}

        if "template" in cfg:
            summary_config["template"] = cfg["template"]
        if "model" in cfg:
            summary_config["model"] = cfg["model"]
        if "emit" in cfg:
            summary_config["emit"] = cfg["emit"]

        actions: list[tuple[str, dict[str, object]]] = [("summary", summary_config)]

        checkpoint = cfg.get("checkpoint")
        if checkpoint is not None:
            actions.append(("checkpoint", {"trigger": checkpoint}))

        return actions


register_step_type(StepTypeName.SUMMARY, SummaryStepType())
