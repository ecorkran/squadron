"""Squash step type — collapse a planning loop's commits into one (slice 948 D6)."""

from __future__ import annotations

from squadron.pipeline.actions import ActionType
from squadron.pipeline.models import StepConfig, ValidationError
from squadron.pipeline.squash import SquashKind
from squadron.pipeline.steps import StepTypeName, register_step_type

# The slice a slice or tasks squash acts on unless it names another (``{slice.index}``).
DEFAULT_SLICE_REF = "{slice}"
KIND_PARAM = "kind"
INDEX_PARAM = "index"
_ALLOWED_KEYS = frozenset({KIND_PARAM, INDEX_PARAM})
_SLICE_SCOPED = frozenset({SquashKind.SLICE, SquashKind.TASKS})


class SquashStepType:
    """Step type that expands to a single ``squash`` action."""

    @property
    def step_type(self) -> str:
        return StepTypeName.SQUASH

    def validate(self, config: StepConfig) -> list[ValidationError]:
        cfg = config.config
        errors = [
            self._error(key, f"unknown key '{key}'; squash accepts {sorted(_ALLOWED_KEYS)}")
            for key in sorted(set(cfg) - _ALLOWED_KEYS)
        ]
        kinds = [k.value for k in SquashKind]
        kind = cfg.get(KIND_PARAM)
        if kind is None:
            errors.append(self._error(KIND_PARAM, f"'{KIND_PARAM}' is required; one of {kinds}"))
        elif kind not in kinds:
            errors.append(self._error(KIND_PARAM, f"'{kind}' is not a squash kind; one of {kinds}"))
        elif INDEX_PARAM not in _with_default_index(cfg):
            errors.append(self._error(INDEX_PARAM, f"a {kind} squash needs '{INDEX_PARAM}'"))
        return errors

    def expand(self, config: StepConfig) -> list[tuple[str, dict[str, object]]]:
        return [(ActionType.SQUASH, _with_default_index(config.config))]

    def _error(self, field: str, message: str) -> ValidationError:
        return ValidationError(field=field, message=message, action_type=self.step_type)


def _with_default_index(cfg: dict[str, object]) -> dict[str, object]:
    """The step's params, with ``index`` defaulted to ``{slice}`` for slice and tasks only."""
    params = dict(cfg)
    if params.get(KIND_PARAM) in _SLICE_SCOPED and INDEX_PARAM not in params:
        params[INDEX_PARAM] = DEFAULT_SLICE_REF
    return params


register_step_type(StepTypeName.SQUASH, SquashStepType())
