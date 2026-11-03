"""Shared utilities for pipeline step type implementations."""

from __future__ import annotations

from collections.abc import Sequence

from squadron.pipeline.models import StepConfig, ValidationError

__all__ = ["any_step_needs_context_forge", "unpack_inner_steps", "validate_allowed_tools"]


def any_step_needs_context_forge(steps: Sequence[StepConfig]) -> bool:
    """True when any of *steps* calls Context Forge (#288); containers answer for their body."""
    # Deferred: the step registry imports the step types, which import this module.
    from squadron.pipeline.steps import bootstrap_step_types, get_step_type, list_step_types

    bootstrap_step_types()
    registered = list_step_types()
    # A step type nobody registered declares nothing, so it keeps the pre-flight.
    return any(
        step.step_type not in registered or get_step_type(step.step_type).needs_context_forge(step)
        for step in steps
    )


def unpack_inner_steps(raw_steps: list[dict[str, object]]) -> list[StepConfig]:
    """Convert raw YAML step list to StepConfig objects.

    Each element is a single-key dict: {step_type: config_or_scalar}.
    """
    result: list[StepConfig] = []
    for index, raw_step in enumerate(raw_steps):
        if len(raw_step) != 1:
            continue
        step_type = str(next(iter(raw_step)))
        raw_config = raw_step[step_type]
        if isinstance(raw_config, dict):
            config: dict[str, object] = {str(k): v for k, v in raw_config.items()}  # type: ignore[union-attr]
        elif raw_config is None:
            config = {}
        else:
            config = {"mode": raw_config}
        name = str(config.pop("name", f"{step_type}-{index}"))
        result.append(StepConfig(step_type=step_type, name=name, config=config))
    return result


def validate_allowed_tools(config: StepConfig, action_type: str) -> list[ValidationError]:
    """Validate a step config's optional ``allowed_tools`` field.

    Absence is valid. When present the value must be a list of strings, each naming a
    tool registered in :mod:`squadron.tools`. Unknown names accumulate one error each so
    a YAML with two typos reports both in a single pass.
    """
    if "allowed_tools" not in config.config:
        return []

    value = config.config["allowed_tools"]
    if not isinstance(value, list):
        return [
            ValidationError(
                field="allowed_tools",
                message="'allowed_tools' must be a list of tool names",
                action_type=action_type,
            )
        ]

    errors: list[ValidationError] = []
    names: list[str] = []
    for entry in value:  # pyright: ignore[reportUnknownVariableType]
        if isinstance(entry, str):
            names.append(entry)
        else:
            errors.append(
                ValidationError(
                    field="allowed_tools",
                    message=(f"'allowed_tools' entries must be strings; got {entry!r}"),
                    action_type=action_type,
                )
            )

    # Imported locally: registering built-ins is an import side effect of this package,
    # which is otherwise reached only through the lazily loaded openai provider. A
    # module-scope import would change import ordering for every step type.
    from squadron import tools

    registered = tools.list_tools()
    for name in names:
        if name not in registered:
            errors.append(
                ValidationError(
                    field="allowed_tools",
                    message=(f"Tool '{name}' is not registered. Available tools: {registered}"),
                    action_type=action_type,
                )
            )
    return errors
