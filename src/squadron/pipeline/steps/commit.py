"""Commit step type — a guarded commit of named paths (#292).

``commit: { paths: [globs], message: "..." }`` stages and commits only changed or
untracked files matching ``paths``, and refuses when any other file changed, when HEAD
moved since the run started, or when the branch is not the integration target.
"""

from __future__ import annotations

from typing import cast

from squadron.pipeline.commit_plan import MESSAGE_PARAM, PATHS_PARAM
from squadron.pipeline.dispatch_keys import path_error
from squadron.pipeline.guarded_commit import GUARDED_PARAM
from squadron.pipeline.models import StepConfig, ValidationError
from squadron.pipeline.steps import StepTypeName, register_step_type

_KNOWN_KEYS = frozenset({PATHS_PARAM, MESSAGE_PARAM})


class CommitStepType:
    """Step type that expands to one guarded commit action."""

    @property
    def step_type(self) -> str:
        return StepTypeName.COMMIT

    @property
    def known_keys(self) -> frozenset[str]:
        return _KNOWN_KEYS

    def validate(self, config: StepConfig) -> list[ValidationError]:
        errors: list[ValidationError] = []
        cfg = config.config

        def fail(field: str, message: str) -> None:
            errors.append(ValidationError(field=field, message=message, action_type=self.step_type))

        paths = cfg.get(PATHS_PARAM)
        if not isinstance(paths, list) or not paths:
            fail(PATHS_PARAM, f"'{PATHS_PARAM}' must be a non-empty list of repo-relative globs")
        else:
            for entry in cast(list[object], paths):
                if not isinstance(entry, str):
                    fail(PATHS_PARAM, f"'{PATHS_PARAM}' entries must be strings, got {entry!r}")
                elif (problem := path_error(entry)) is not None:
                    fail(PATHS_PARAM, problem)
        message = cfg.get(MESSAGE_PARAM)
        if not isinstance(message, str) or not message.strip():
            fail(MESSAGE_PARAM, f"'{MESSAGE_PARAM}' must be a non-empty string")
        return errors

    def needs_context_forge(self, config: StepConfig) -> bool:
        """Reads the integration target from Context Forge."""
        return True

    def expand(self, config: StepConfig) -> list[tuple[str, dict[str, object]]]:
        cfg = config.config
        return [
            (
                "commit",
                {
                    PATHS_PARAM: cfg[PATHS_PARAM],
                    MESSAGE_PARAM: cfg[MESSAGE_PARAM],
                    GUARDED_PARAM: True,
                },
            )
        ]


register_step_type(StepTypeName.COMMIT, CommitStepType())
