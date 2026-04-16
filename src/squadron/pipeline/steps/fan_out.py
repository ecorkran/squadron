"""FanOutStepType — dispatches N parallel branches then reduces via FanInReducer."""

from __future__ import annotations

from squadron.pipeline.intelligence.fan_in.reducers import get_reducer
from squadron.pipeline.models import StepConfig, ValidationError
from squadron.pipeline.steps import StepTypeName, register_step_type

_POOL_PREFIX = "pool:"


class FanOutStepType:
    """Step type for concurrent multi-model branch dispatch with fan-in reduction.

    ``expand()`` returns [] — the executor handles fan_out directly via
    ``_execute_fan_out_step``, mirroring the ``each`` step pattern.
    """

    @property
    def step_type(self) -> str:
        return StepTypeName.FAN_OUT

    def validate(self, config: StepConfig) -> list[ValidationError]:
        errors: list[ValidationError] = []
        cfg = config.config
        step_type = self.step_type

        # 1. models must be present
        if "models" not in cfg:
            errors.append(
                ValidationError(
                    field="models",
                    message="'models' is required",
                    action_type=step_type,
                )
            )

        # 2. inner must be present and parseable as a single-key dict
        inner_raw = cfg.get("inner")
        if inner_raw is None:
            errors.append(
                ValidationError(
                    field="inner",
                    message="'inner' is required",
                    action_type=step_type,
                )
            )
        elif not isinstance(inner_raw, dict) or len(inner_raw) != 1:  # type: ignore[arg-type]
            errors.append(
                ValidationError(
                    field="inner",
                    message=(
                        "'inner' must be a single-key dict (e.g. {dispatch: {...}})"
                    ),
                    action_type=step_type,
                )
            )
        else:
            # 3. Inner step type must not be fan_out (no nesting)
            inner_type = str(next(iter(inner_raw)))  # type: ignore[arg-type]
            if inner_type == StepTypeName.FAN_OUT:
                errors.append(
                    ValidationError(
                        field="inner",
                        message="nested 'fan_out' is not allowed as an inner step type",
                        action_type=step_type,
                    )
                )

        # 4. If models is a pool ref, n must be a positive integer
        models_raw = cfg.get("models")
        if isinstance(models_raw, str) and models_raw.startswith(_POOL_PREFIX):
            n = cfg.get("n")
            if n is None or not isinstance(n, int) or n < 1:
                errors.append(
                    ValidationError(
                        field="n",
                        message=(
                            "'n' is required and must be a positive integer "
                            "when 'models' is a pool reference"
                        ),
                        action_type=step_type,
                    )
                )

        # 5. fan_in, if present, must be a registered reducer name
        fan_in_name = cfg.get("fan_in")
        if fan_in_name is not None:
            try:
                get_reducer(str(fan_in_name))
            except KeyError:
                errors.append(
                    ValidationError(
                        field="fan_in",
                        message=f"'{fan_in_name}' is not a registered fan-in reducer",
                        action_type=step_type,
                    )
                )

        return errors

    def expand(self, config: StepConfig) -> list[tuple[str, dict[str, object]]]:
        # Fan-out is executed directly by the executor; no actions to expand.
        return []


register_step_type(StepTypeName.FAN_OUT, FanOutStepType())
