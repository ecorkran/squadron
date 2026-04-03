"""Pydantic v2 schema models for pipeline YAML validation.

Validates raw YAML into typed structures, then converts to the existing
PipelineDefinition / StepConfig dataclasses that the executor consumes.
"""

from __future__ import annotations

from typing import Any, cast

from pydantic import BaseModel, ConfigDict, model_validator

from squadron.pipeline.models import PipelineDefinition, StepConfig


def _expand_step_config(raw_config: Any) -> dict[str, object]:
    """Expand a raw step config value into a dict.

    Scalar values become ``{"mode": value}``; dicts pass through;
    None becomes empty dict.
    """
    if isinstance(raw_config, dict):
        return dict(cast(dict[str, object], raw_config))
    if raw_config is None:
        return {}
    return {"mode": raw_config}


class StepSchema(BaseModel):
    """Single step as parsed from YAML."""

    step_type: str
    name: str | None = None
    config: dict[str, object]


class PipelineSchema(BaseModel):
    """Top-level pipeline definition validated from YAML.

    Accepts the raw YAML structure where each step is a single-key dict
    mapping step_type -> config.  A ``@model_validator(mode="before")``
    unpacks the raw steps list into ``StepSchema`` instances.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""
    params: dict[str, str] = {}
    model: str | None = None
    steps: list[StepSchema]

    @model_validator(mode="before")
    @classmethod
    def _unpack_steps(cls, data: Any) -> Any:
        """Transform the raw YAML step list into StepSchema-compatible dicts.

        Each step in YAML is ``{type_name: config_or_scalar}``.
        A scalar value (e.g. ``"auto"``) is expanded to ``{"mode": value}``.
        """
        if not isinstance(data, dict):
            return data

        values = cast(dict[str, Any], data)
        raw_steps_val = values.get("steps")
        if not isinstance(raw_steps_val, list):
            return values

        raw_steps = cast(list[Any], raw_steps_val)
        if len(raw_steps) == 0:
            return values
        unpacked: list[dict[str, Any]] = []
        for raw_step in raw_steps:
            if not isinstance(raw_step, dict):
                msg = f"Each step must be a single-key mapping, got: {raw_step!r}"
                raise ValueError(msg)

            step = cast(dict[str, Any], raw_step)
            if "step_type" in step:
                # Already in StepSchema form (e.g. from programmatic use)
                unpacked.append(step)
                continue

            if len(step) != 1:
                msg = f"Each step must be a single-key mapping, got: {step!r}"
                raise ValueError(msg)

            step_type: str = str(next(iter(step)))
            raw_config: Any = step[step_type]

            config = _expand_step_config(raw_config)

            # Extract explicit name from config if present
            name = config.pop("name", None)
            unpacked.append(
                {
                    "step_type": step_type,
                    "name": name,
                    "config": config,
                }
            )

        result = dict(values)
        result["steps"] = unpacked
        return result

    @model_validator(mode="after")
    def _validate_steps_non_empty(self) -> PipelineSchema:
        """Ensure the pipeline has at least one step."""
        if len(self.steps) == 0:
            msg = "Pipeline must have at least one step"
            raise ValueError(msg)
        return self

    def to_definition(self) -> PipelineDefinition:
        """Convert validated schema to runtime PipelineDefinition."""
        steps: list[StepConfig] = []
        for index, step in enumerate(self.steps):
            name = step.name if step.name else f"{step.step_type}-{index}"
            steps.append(
                StepConfig(
                    step_type=step.step_type,
                    name=name,
                    config=dict(step.config),
                )
            )

        return PipelineDefinition(
            name=self.name,
            description=self.description,
            params=dict(self.params),
            steps=steps,
            model=self.model,
        )
