"""Gate step type — reduces a judge result and a review result, then optional checkpoint."""

from __future__ import annotations

from squadron.pipeline.actions.checkpoint import CheckpointTrigger
from squadron.pipeline.actions.gate import VALID_GATE_POLICIES
from squadron.pipeline.models import StepConfig, ValidationError
from squadron.pipeline.steps import StepTypeName, register_step_type


class GateStepType:
    """Step type that expands to a gate action and optional checkpoint.

    Own-config validation only (presence/type of judge_from, review_from,
    policy): checking that the named steps actually exist is a cross-step
    concern the loader handles (see loader._validate_gate_references).
    """

    @property
    def step_type(self) -> str:
        return StepTypeName.GATE

    def validate(self, config: StepConfig) -> list[ValidationError]:
        errors: list[ValidationError] = []
        cfg = config.config

        for field in ("judge_from", "review_from"):
            value = cfg.get(field)
            if value is None:
                errors.append(
                    ValidationError(
                        field=field,
                        message=f"'{field}' is required",
                        action_type=self.step_type,
                    )
                )
            elif not isinstance(value, str):
                errors.append(
                    ValidationError(
                        field=field,
                        message=f"'{field}' must be a string",
                        action_type=self.step_type,
                    )
                )

        policy = cfg.get("policy")
        if policy is not None and policy not in VALID_GATE_POLICIES:
            errors.append(
                ValidationError(
                    field="policy",
                    message=(
                        f"'{policy}' is not a valid gate policy. "
                        f"Valid values: {sorted(VALID_GATE_POLICIES)}"
                    ),
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

        gate_dict: dict[str, object] = {
            "judge_from": cfg["judge_from"],
            "review_from": cfg["review_from"],
        }
        if "policy" in cfg:
            gate_dict["policy"] = cfg["policy"]

        actions: list[tuple[str, dict[str, object]]] = [
            ("gate", gate_dict),
        ]

        if "checkpoint" in cfg:
            actions.append(("checkpoint", {"trigger": cfg["checkpoint"]}))

        return actions


register_step_type(StepTypeName.GATE, GateStepType())
