"""Gate step type — resolves a verdict under a gate policy, then optional checkpoint."""

from __future__ import annotations

from typing import cast

from squadron.pipeline.actions.checkpoint import CheckpointTrigger
from squadron.pipeline.actions.gate import (
    DEFAULT_GATE_POLICY,
    JUDGE_BLOCK_KEYS,
    VALID_GATE_POLICIES,
    GatePolicyContract,
    policy_contract,
)
from squadron.pipeline.models import StepConfig, ValidationError
from squadron.pipeline.steps import StepTypeName, register_step_type

_JUDGE_FIELD = "judge"


class GateStepType:
    """Step type that expands to a gate action and optional checkpoint.

    Own-config validation only (presence/type of the policy's reference fields,
    the policy itself, and the optional judge: block): checking that the named
    steps actually exist is a cross-step concern the loader handles (see
    loader._validate_gate_references) or, for loop bodies, LoopStepType.
    """

    @property
    def step_type(self) -> str:
        return StepTypeName.GATE

    def validate(self, config: StepConfig) -> list[ValidationError]:
        errors: list[ValidationError] = []
        cfg = config.config

        policy = cfg.get("policy")
        contract = policy_contract(policy)
        if contract is None:
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
        else:
            errors.extend(self._validate_reference_fields(cfg, contract, policy))
            errors.extend(self._validate_judge_block(cfg, contract, policy))

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

    def _validate_reference_fields(
        self,
        cfg: dict[str, object],
        contract: GatePolicyContract,
        policy: object,
    ) -> list[ValidationError]:
        """Check the reference fields this policy requires, and reject the ones it forbids."""
        errors: list[ValidationError] = []

        for field in contract.required:
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

        for field in contract.forbidden:
            if field in cfg:
                errors.append(
                    ValidationError(
                        field=field,
                        message=(f"'{field}' is not accepted by gate policy '{_policy_label(policy)}'"),
                        action_type=self.step_type,
                    )
                )

        return errors

    def _validate_judge_block(
        self,
        cfg: dict[str, object],
        contract: GatePolicyContract,
        policy: object,
    ) -> list[ValidationError]:
        """Check the optional `judge:` block — a mapping of accepted keys only."""
        if _JUDGE_FIELD not in cfg:
            return []

        if not contract.supports_judge_block:
            return [
                ValidationError(
                    field=_JUDGE_FIELD,
                    message=(
                        f"gate policy '{_policy_label(policy)}' has no model layer, "
                        f"so it accepts no '{_JUDGE_FIELD}:' block"
                    ),
                    action_type=self.step_type,
                )
            ]

        judge = cfg[_JUDGE_FIELD]
        if not isinstance(judge, dict):
            return [
                ValidationError(
                    field=_JUDGE_FIELD,
                    message=f"'{_JUDGE_FIELD}' must be a mapping",
                    action_type=self.step_type,
                )
            ]

        errors: list[ValidationError] = []
        judge_block = cast(dict[object, object], judge)
        for key, value in judge_block.items():
            if key not in JUDGE_BLOCK_KEYS:
                errors.append(
                    ValidationError(
                        field=f"{_JUDGE_FIELD}.{key}",
                        message=(
                            f"'{key}' is not a valid {_JUDGE_FIELD}: key. "
                            f"Valid keys: {sorted(JUDGE_BLOCK_KEYS)}"
                        ),
                        action_type=self.step_type,
                    )
                )
            elif not isinstance(value, str):
                errors.append(
                    ValidationError(
                        field=f"{_JUDGE_FIELD}.{key}",
                        message=f"'{key}' must be a string",
                        action_type=self.step_type,
                    )
                )
        return errors

    def expand(self, config: StepConfig) -> list[tuple[str, dict[str, object]]]:
        cfg = config.config

        # Build from the fields this policy actually declares — an
        # unconditional cfg["judge_from"] would KeyError on a valid
        # findings-addressed step, which has no judge leg.
        contract = policy_contract(cfg.get("policy"))
        declared_fields = contract.required if contract is not None else ()

        gate_dict: dict[str, object] = {field: cfg[field] for field in declared_fields if field in cfg}
        if "policy" in cfg:
            gate_dict["policy"] = cfg["policy"]
        if _JUDGE_FIELD in cfg:
            gate_dict[_JUDGE_FIELD] = cfg[_JUDGE_FIELD]

        actions: list[tuple[str, dict[str, object]]] = [
            ("gate", gate_dict),
        ]

        if "checkpoint" in cfg:
            actions.append(("checkpoint", {"trigger": cfg["checkpoint"]}))

        return actions


def _policy_label(policy: object) -> str:
    """Render the policy for an error message, naming the default when unset."""
    return str(policy) if policy is not None else DEFAULT_GATE_POLICY


register_step_type(StepTypeName.GATE, GateStepType())
