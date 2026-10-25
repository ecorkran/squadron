"""Squash step type — collapse a planning loop's commits into one (slice 948 D6)."""

from __future__ import annotations

from squadron.pipeline.actions import ActionType
from squadron.pipeline.commit_plan import PLAN_PARAM, SLICE_PARAM, CommitSubject
from squadron.pipeline.models import StepConfig, ValidationError
from squadron.pipeline.squash import check_squash_scope
from squadron.pipeline.steps import StepTypeName, register_step_type

# The slice a design or tasks squash acts on unless it names another (``{slice.index}``).
DEFAULT_SLICE_REF = "{slice}"
SUBJECT_PARAM = "subject"
_ALLOWED_KEYS = frozenset({SUBJECT_PARAM, SLICE_PARAM, PLAN_PARAM})
_SLICE_SCOPED = frozenset({CommitSubject.DESIGN, CommitSubject.TASKS})


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
        subject = cfg.get(SUBJECT_PARAM)
        if subject is None:
            errors.append(self._error(SUBJECT_PARAM, f"'{SUBJECT_PARAM}' is required"))
            return errors
        params = _with_default_slice(cfg)
        try:
            check_squash_scope(str(subject), SLICE_PARAM in params, PLAN_PARAM in params)
        except ValueError as exc:
            errors.append(self._error(SUBJECT_PARAM, str(exc)))
        return errors

    def expand(self, config: StepConfig) -> list[tuple[str, dict[str, object]]]:
        return [(ActionType.SQUASH, _with_default_slice(config.config))]

    def _error(self, field: str, message: str) -> ValidationError:
        return ValidationError(field=field, message=message, action_type=self.step_type)


def _with_default_slice(cfg: dict[str, object]) -> dict[str, object]:
    """The step's params, with ``slice`` defaulted to ``{slice}`` for design and tasks only."""
    params = dict(cfg)
    if params.get(SUBJECT_PARAM) in _SLICE_SCOPED and SLICE_PARAM not in params:
        params[SLICE_PARAM] = DEFAULT_SLICE_REF
    return params


register_step_type(StepTypeName.SQUASH, SquashStepType())
