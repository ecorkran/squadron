"""Phase step type — expands a named phase into a sequence of actions."""

from __future__ import annotations

from typing import cast

from squadron.pipeline.actions.checkpoint import CheckpointTrigger
from squadron.pipeline.models import StepConfig, ValidationError
from squadron.pipeline.steps import StepTypeName, register_step_type


class PhaseStepType:
    """Step type for design, tasks, and implement phases.

    Expands to: cf-op(set_phase) -> cf-op(build) -> dispatch
    -> [review -> checkpoint] -> commit.
    Review and checkpoint are included only when review is configured.
    """

    def __init__(self, phase_name: str) -> None:
        self._phase_name = phase_name

    @property
    def step_type(self) -> str:
        return self._phase_name

    def validate(self, config: StepConfig) -> list[ValidationError]:
        errors: list[ValidationError] = []
        cfg = config.config

        phase = cfg.get("phase")
        if phase is None:
            errors.append(
                ValidationError(
                    field="phase",
                    message="'phase' is required",
                    action_type=self._phase_name,
                )
            )
        elif not isinstance(phase, int):
            errors.append(
                ValidationError(
                    field="phase",
                    message="'phase' must be an integer",
                    action_type=self._phase_name,
                )
            )

        review = cfg.get("review")
        if review is not None:
            if isinstance(review, dict):
                if "template" not in cast(dict[str, object], review):
                    errors.append(
                        ValidationError(
                            field="review",
                            message="review dict must contain 'template' key",
                            action_type=self._phase_name,
                        )
                    )
            elif not isinstance(review, str):
                errors.append(
                    ValidationError(
                        field="review",
                        message="'review' must be a string or dict with 'template' key",
                        action_type=self._phase_name,
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
                        action_type=self._phase_name,
                    )
                )

        model = cfg.get("model")
        if model is not None and not isinstance(model, str):
            errors.append(
                ValidationError(
                    field="model",
                    message="'model' must be a string",
                    action_type=self._phase_name,
                )
            )

        return errors

    def expand(self, config: StepConfig) -> list[tuple[str, dict[str, object]]]:
        cfg = config.config
        phase = cfg["phase"]
        model = cfg.get("model")

        actions: list[tuple[str, dict[str, object]]] = [
            ("cf-op", {"operation": "set_phase", "phase": phase}),
            ("cf-op", {"operation": "set_slice", "slice": "{slice}"}),
            ("cf-op", {"operation": "build_context"}),
            ("dispatch", {"model": model}),
        ]

        review = cfg.get("review")
        if review is not None:
            if isinstance(review, str):
                actions.append(("review", {"template": review, "model": None}))
            elif isinstance(review, dict):
                review_dict = cast(dict[str, object], review)
                actions.append(
                    (
                        "review",
                        {
                            "template": review_dict["template"],
                            "model": review_dict.get("model"),
                        },
                    )
                )

            checkpoint = cfg.get("checkpoint", CheckpointTrigger.NEVER)
            actions.append(("checkpoint", {"trigger": checkpoint}))

        actions.append(("commit", {"message_prefix": f"phase-{phase}"}))

        return actions


register_step_type(StepTypeName.DESIGN, PhaseStepType("design"))
register_step_type(StepTypeName.TASKS, PhaseStepType("tasks"))
register_step_type(StepTypeName.IMPLEMENT, PhaseStepType("implement"))
