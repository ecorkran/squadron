"""Shared utilities for pipeline step type implementations."""

from __future__ import annotations

from squadron.pipeline.models import StepConfig

__all__ = ["unpack_inner_steps"]


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
