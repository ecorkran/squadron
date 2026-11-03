"""Dispatch step type — expands a dispatch config into a single dispatch action."""

from __future__ import annotations

from typing import cast

from squadron.pipeline.actions.dispatch import DispatchFeedback
from squadron.pipeline.dispatch_keys import (
    DELIVERED_PROMPT_FILE_KEY,
    DISPATCH_IO_KEYS,
    PROMPT_FILES_KEY,
    REPLY_FILE_KEY,
    REPLY_FORMAT_KEY,
    REPLY_FROM_KEY,
    ReplyFormat,
    path_error,
)
from squadron.pipeline.models import StepConfig, ValidationError
from squadron.pipeline.steps import StepTypeName, register_step_type
from squadron.pipeline.steps.phase import ArtifactKind, PhaseStepType
from squadron.pipeline.steps.utils import validate_allowed_tools

#: Optional dispatch-step key naming the artifact the dispatch rewrites (a loop's
#: revise step). It gives the step an expected artifact kind, as a phase step has.
ARTIFACT_KEY = "artifact"

#: Dispatch-step keys ``expand`` forwards to the dispatch action.
DISPATCH_FORWARDED_KEYS: tuple[str, ...] = (
    "prompt",
    "model",
    "pre_emption_fragment",
    "allowed_tools",
    "feedback",
    *DISPATCH_IO_KEYS,
)

_KNOWN_KEYS = frozenset(DISPATCH_FORWARDED_KEYS) | {ARTIFACT_KEY}


class DispatchStepType:
    """Step type that expands to a single dispatch action.

    Accepts an optional ``prompt`` and optional ``model``. When ``prompt`` is
    absent the dispatch action falls back to the most recent ``build_context``
    output — the same behaviour as the dispatch action produced by phase steps.
    """

    @property
    def step_type(self) -> str:
        return StepTypeName.DISPATCH

    @property
    def known_keys(self) -> frozenset[str]:
        return _KNOWN_KEYS

    def validate(self, config: StepConfig) -> list[ValidationError]:
        errors: list[ValidationError] = []
        cfg = config.config

        prompt = cfg.get("prompt")
        if prompt is not None and not isinstance(prompt, str):
            errors.append(
                ValidationError(
                    field="prompt",
                    message="'prompt' must be a string",
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

        fragment = cfg.get("pre_emption_fragment")
        if fragment is not None and not isinstance(fragment, str):
            errors.append(
                ValidationError(
                    field="pre_emption_fragment",
                    message="'pre_emption_fragment' must be a string",
                    action_type=self.step_type,
                )
            )

        feedback = cfg.get("feedback")
        if feedback is not None and feedback not in DispatchFeedback.__members__.values():
            valid = [f.value for f in DispatchFeedback]
            errors.append(
                ValidationError(
                    field="feedback",
                    message=f"'feedback' must be one of {valid}, got: {feedback!r}",
                    action_type=self.step_type,
                )
            )

        artifact = cfg.get(ARTIFACT_KEY)
        if artifact is not None and artifact not in ArtifactKind.__members__.values():
            valid = [k.value for k in ArtifactKind]
            errors.append(
                ValidationError(
                    field=ARTIFACT_KEY,
                    message=f"'{ARTIFACT_KEY}' must be one of {valid}, got: {artifact!r}",
                    action_type=self.step_type,
                )
            )

        errors.extend(validate_allowed_tools(config, self.step_type))
        errors.extend(self._validate_io_keys(cfg))

        return errors

    def _validate_io_keys(self, cfg: dict[str, object]) -> list[ValidationError]:
        """Shape checks for the file and reply keys (slice 949 D1)."""
        errors: list[ValidationError] = []

        def fail(field: str, message: str) -> None:
            errors.append(ValidationError(field=field, message=message, action_type=self.step_type))

        def check_path(field: str, value: object) -> None:
            if not isinstance(value, str):
                fail(field, f"'{field}' entries must be strings, got: {value!r}")
            elif "{" not in value and (problem := path_error(value)) is not None:
                # A {param} value is checked by the same function once it resolves.
                fail(field, f"'{field}': {problem}")

        if PROMPT_FILES_KEY in cfg:
            files = cfg[PROMPT_FILES_KEY]
            if isinstance(files, str):
                fail(
                    PROMPT_FILES_KEY,
                    f"'{PROMPT_FILES_KEY}' must be a list of paths, not a single string",
                )
            elif not isinstance(files, list) or not files:
                fail(PROMPT_FILES_KEY, f"'{PROMPT_FILES_KEY}' must be a non-empty list of paths")
            else:
                for entry in cast(list[object], files):
                    check_path(PROMPT_FILES_KEY, entry)

        if REPLY_FORMAT_KEY in cfg and cfg[REPLY_FORMAT_KEY] not in ReplyFormat.__members__.values():
            valid = [f.value for f in ReplyFormat]
            fail(
                REPLY_FORMAT_KEY,
                f"'{REPLY_FORMAT_KEY}' must be one of {valid}, got: {cfg[REPLY_FORMAT_KEY]!r}",
            )

        reply_from = cfg.get(REPLY_FROM_KEY)
        if REPLY_FROM_KEY in cfg and (not isinstance(reply_from, str) or not reply_from):
            fail(REPLY_FROM_KEY, f"'{REPLY_FROM_KEY}' must be the name of an earlier dispatch step")

        for key in (REPLY_FILE_KEY, DELIVERED_PROMPT_FILE_KEY):
            if key in cfg:
                check_path(key, cfg[key])
        if REPLY_FILE_KEY in cfg and cfg.get(REPLY_FILE_KEY) == cfg.get(DELIVERED_PROMPT_FILE_KEY):
            fail(REPLY_FILE_KEY, f"'{REPLY_FILE_KEY}' and '{DELIVERED_PROMPT_FILE_KEY}' must differ")

        # The feedback prompt is built from review findings; a second prompt source would conflict.
        if "feedback" in cfg:
            for key in (PROMPT_FILES_KEY, REPLY_FROM_KEY):
                if key in cfg:
                    fail("feedback", f"'feedback' cannot be combined with '{key}'")

        return errors

    def needs_context_forge(self, config: StepConfig) -> bool:
        """Only a dispatch that declares an ``artifact`` kind resolves it through Context Forge."""
        return ARTIFACT_KEY in config.config

    def expand(self, config: StepConfig) -> list[tuple[str, dict[str, object]]]:
        cfg = config.config
        # Only pass keys that are explicitly set — absent keys let the dispatch
        # action use its own resolution logic (e.g. prompt from build_context).
        action_config: dict[str, object] = {
            key: cfg[key] for key in DISPATCH_FORWARDED_KEYS if key in cfg
        }

        return [("dispatch", action_config)]


def step_artifact_kind(step_type_impl: object, step: StepConfig) -> ArtifactKind | None:
    """The artifact kind a step's dispatch is expected to write, or None.

    A phase step knows it from its phase; a dispatch step declares it with ``artifact:``.
    """
    if isinstance(step_type_impl, PhaseStepType):
        return step_type_impl.expected_artifact_kind
    declared = step.config.get(ARTIFACT_KEY)
    if isinstance(step_type_impl, DispatchStepType) and declared is not None:
        return ArtifactKind(str(declared))
    return None


register_step_type(StepTypeName.DISPATCH, DispatchStepType())
