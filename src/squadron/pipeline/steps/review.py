"""Review step type — standalone review with optional checkpoint."""

from __future__ import annotations

from squadron.pipeline.actions.checkpoint import CheckpointTrigger
from squadron.pipeline.models import StepConfig, ValidationError
from squadron.pipeline.steps import StepTypeName, register_step_type
from squadron.pipeline.steps.utils import validate_allowed_tools


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

        errors.extend(validate_allowed_tools(config, self.step_type))

        return errors

    def expand(self, config: StepConfig) -> list[tuple[str, dict[str, object]]]:
        cfg = config.config

        review_dict: dict[str, object] = {
            "template": cfg["template"],
            "model": cfg.get("model"),
        }
        if "slice" in cfg:
            review_dict["slice"] = cfg["slice"]
        if "judge" in cfg:
            review_dict["judge"] = cfg["judge"]
        if "allowed_tools" in cfg:
            review_dict["allowed_tools"] = cfg["allowed_tools"]

        actions: list[tuple[str, dict[str, object]]] = [
            ("review", review_dict),
        ]

        if "checkpoint" in cfg:
            actions.append(("checkpoint", {"trigger": cfg["checkpoint"]}))

        return actions


register_step_type(StepTypeName.REVIEW, ReviewStepType())
