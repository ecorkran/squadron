"""Branch step type — enter or merge a slice's branch (slice 196 D4)."""

from __future__ import annotations

from enum import StrEnum

from squadron.pipeline.commit_plan import SLICE_PARAM
from squadron.pipeline.models import StepConfig, ValidationError
from squadron.pipeline.steps import StepTypeName, register_step_type

# The slice a branch step acts on unless it names another (for example ``{slice.index}``).
DEFAULT_SLICE_REF = "{slice}"


class BranchOp(StrEnum):
    """What a branch step does."""

    ENTER = "enter"
    MERGE = "merge"


# The action param naming the op; the slice uses the shared ``SLICE_PARAM``.
OP_PARAM = "op"
_ALLOWED_KEYS = frozenset({OP_PARAM, SLICE_PARAM})


class BranchStepType:
    """Step type that expands to a single ``branch`` action."""

    @property
    def step_type(self) -> str:
        return StepTypeName.BRANCH

    def validate(self, config: StepConfig) -> list[ValidationError]:
        errors: list[ValidationError] = []
        cfg = config.config

        op = cfg.get(OP_PARAM)
        valid_ops = [o.value for o in BranchOp]
        if op is None:
            errors.append(self._error(OP_PARAM, f"'{OP_PARAM}' is required; one of {valid_ops}"))
        elif op not in valid_ops:
            errors.append(self._error(OP_PARAM, f"'{op}' is not a valid branch op; one of {valid_ops}"))

        for key in sorted(set(cfg) - _ALLOWED_KEYS):
            errors.append(
                self._error(key, f"unknown key '{key}'; branch accepts {sorted(_ALLOWED_KEYS)}")
            )
        return errors

    def expand(self, config: StepConfig) -> list[tuple[str, dict[str, object]]]:
        cfg = config.config
        return [
            (
                "branch",
                {
                    OP_PARAM: BranchOp(str(cfg[OP_PARAM])),
                    SLICE_PARAM: cfg.get(SLICE_PARAM, DEFAULT_SLICE_REF),
                },
            )
        ]

    def _error(self, field: str, message: str) -> ValidationError:
        return ValidationError(field=field, message=message, action_type=self.step_type)


register_step_type(StepTypeName.BRANCH, BranchStepType())
