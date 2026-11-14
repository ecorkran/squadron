"""Fix step type: fix an issue with a test, a change, the gates and one commit (slice 423 D1).

Expands to ``fix-context`` (issue text, preconditions, prompt), ``dispatch`` (the agent)
and ``commit`` with the ``fix`` subject (the checked report becomes one commit).
"""

from __future__ import annotations

import re

from squadron.pipeline.actions import ActionType
from squadron.pipeline.commit_plan import SUBJECT_PARAM, CommitSubject
from squadron.pipeline.dispatch_keys import path_error
from squadron.pipeline.fix_issue import parse_issue_ref
from squadron.pipeline.fix_keys import (
    COMMIT_TO_PARAM,
    COMMIT_TO_VALUES,
    ISSUE_FILE_PARAM,
    ISSUE_PARAM,
)
from squadron.pipeline.models import StepConfig, ValidationError
from squadron.pipeline.steps import StepTypeName, register_step_type

MODEL_KEY = "model"
_ALLOWED_KEYS = frozenset({ISSUE_PARAM, MODEL_KEY, ISSUE_FILE_PARAM, COMMIT_TO_PARAM})
# A value that is exactly one ``{name}`` token is a param still to be bound (the loader
# validates before params are bound); the resolved value is checked when the action runs.
_PLACEHOLDER = re.compile(r"\{[A-Za-z0-9_.\-]+\}")


def _is_placeholder(value: object) -> bool:
    return isinstance(value, str) and _PLACEHOLDER.fullmatch(value.strip()) is not None


class FixStepType:
    """Step type that expands to ``fix-context``, ``dispatch`` and a ``fix`` commit."""

    @property
    def step_type(self) -> str:
        return StepTypeName.FIX

    @property
    def known_keys(self) -> frozenset[str]:
        return _ALLOWED_KEYS

    def validate(self, config: StepConfig) -> list[ValidationError]:
        cfg = config.config
        errors: list[ValidationError] = []

        for key in (ISSUE_PARAM, COMMIT_TO_PARAM):
            if key not in cfg:
                errors.append(self._error(key, f"'{key}' is required"))
        if ISSUE_PARAM in cfg and not _is_placeholder(cfg[ISSUE_PARAM]):
            try:
                parse_issue_ref(str(cfg[ISSUE_PARAM]))
            except ValueError as exc:
                errors.append(self._error(ISSUE_PARAM, str(exc)))
        commit_to = cfg.get(COMMIT_TO_PARAM)
        if commit_to is not None and not _is_placeholder(commit_to):
            if commit_to not in COMMIT_TO_VALUES:
                allowed = list(COMMIT_TO_VALUES)
                errors.append(self._error(COMMIT_TO_PARAM, f"'{commit_to}' is not one of {allowed}"))
        errors.extend(self._validate_issue_file(cfg))
        model = cfg.get(MODEL_KEY)
        if model is not None and not isinstance(model, str):
            errors.append(self._error(MODEL_KEY, f"'{MODEL_KEY}' must be a string, got {model!r}"))
        for key in sorted(set(cfg) - _ALLOWED_KEYS):
            errors.append(self._error(key, f"unknown key '{key}'; fix accepts {sorted(_ALLOWED_KEYS)}"))
        return errors

    def _validate_issue_file(self, cfg: dict[str, object]) -> list[ValidationError]:
        value = cfg.get(ISSUE_FILE_PARAM)
        if value is None or _is_placeholder(value):
            return []
        if not isinstance(value, str):
            return [self._error(ISSUE_FILE_PARAM, f"'{ISSUE_FILE_PARAM}' must be a string")]
        # An empty value is the documented fetch mode, not a missing path.
        if value and (problem := path_error(value)) is not None:
            return [self._error(ISSUE_FILE_PARAM, f"'{ISSUE_FILE_PARAM}': {problem}")]
        return []

    def needs_context_forge(self, config: StepConfig) -> bool:
        """False: cf is read only under ``commit-to: target``, where reading it fails the
        action with a clear message, so a ``current`` run in a bare repository needs none."""
        return False

    def expand(self, config: StepConfig) -> list[tuple[str, dict[str, object]]]:
        cfg = config.config
        context_params: dict[str, object] = {
            ISSUE_PARAM: cfg[ISSUE_PARAM],
            COMMIT_TO_PARAM: cfg[COMMIT_TO_PARAM],
        }
        if ISSUE_FILE_PARAM in cfg:
            context_params[ISSUE_FILE_PARAM] = cfg[ISSUE_FILE_PARAM]
        return [
            (ActionType.FIX_CONTEXT, context_params),
            (ActionType.DISPATCH, {MODEL_KEY: cfg.get(MODEL_KEY)}),
            (ActionType.COMMIT, {SUBJECT_PARAM: CommitSubject.FIX}),
        ]

    def _error(self, field: str, message: str) -> ValidationError:
        return ValidationError(field=field, message=message, action_type=self.step_type)


register_step_type(StepTypeName.FIX, FixStepType())
