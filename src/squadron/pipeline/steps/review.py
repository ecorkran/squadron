"""Review step type — standalone review with optional checkpoint."""

from __future__ import annotations

from squadron.pipeline.actions.checkpoint import CheckpointTrigger
from squadron.pipeline.models import StepConfig, ValidationError
from squadron.pipeline.steps import StepTypeName, register_step_type


class ReviewStepType:
    """Step type that expands to a review action and optional checkpoint."""

    @property
    def step_type(self) -> str:
        return StepTypeName.REVIEW

    def validate(self, config: StepConfig) -> list[ValidationError]:
        errors: list[ValidationError] = []
        cfg = config.config

        if "template" not in cfg:
            errors.append(
                ValidationError(
                    field="template",
                    message="'template' is required",
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

        model = cfg.get("model")
        if model is not None and not isinstance(model, str):
            errors.append(
                ValidationError(
                    field="model",
                    message="'model' must be a string",
                    action_type=self.step_type,
                )
            )

        return errors

    def expand(self, config: StepConfig) -> list[tuple[str, dict[str, object]]]:
        cfg = config.config

        actions: list[tuple[str, dict[str, object]]] = [
            ("review", {"template": cfg["template"], "model": cfg.get("model")}),
        ]

        if "checkpoint" in cfg:
            actions.append(("checkpoint", {"trigger": cfg["checkpoint"]}))

        return actions


register_step_type(StepTypeName.REVIEW, ReviewStepType())
