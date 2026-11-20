"""ProducerStep protocol and the reserved producer-only param (slice 424, Task 3)."""

from __future__ import annotations

import pytest

from squadron.pipeline.control_params import (
    RESERVED_PARAMS,
    RUN_PRODUCER_ONLY,
    reserved_param_error,
)
from squadron.pipeline.models import PipelineDefinition, StepConfig
from squadron.pipeline.producer_only import ProducerStep


class _WithMethod:
    def producer_only_config(self, config: StepConfig) -> StepConfig:
        return config


class _WithoutMethod:
    pass


def test_producer_only_param_is_reserved() -> None:
    assert RUN_PRODUCER_ONLY in RESERVED_PARAMS
    assert reserved_param_error(RUN_PRODUCER_ONLY) == (
        f"'{RUN_PRODUCER_ONLY}' is reserved; use --producer-only"
    )


def test_producer_only_param_cannot_be_set_through_p() -> None:
    from typer import BadParameter

    from squadron.cli.commands.run import _apply_param_overrides

    params: dict[str, object] = {}
    with pytest.raises(BadParameter, match="--producer-only"):
        _apply_param_overrides(params, [f"{RUN_PRODUCER_ONLY}=true"])
    assert params == {}


def test_class_with_the_method_is_a_producer_step() -> None:
    assert isinstance(_WithMethod(), ProducerStep)


def test_class_without_the_method_is_not_a_producer_step() -> None:
    assert not isinstance(_WithoutMethod(), ProducerStep)


def test_pipeline_params_block_rejects_the_reserved_key() -> None:
    from squadron.pipeline.loader import validate_pipeline

    definition = PipelineDefinition(
        name="p",
        description="",
        params={"slice": "required", RUN_PRODUCER_ONLY: "x"},
        steps=[StepConfig(step_type="devlog", name="devlog-0", config={"mode": "auto"})],
    )
    errors = validate_pipeline(definition, cwd=".")
    assert any(e.field == f"params.{RUN_PRODUCER_ONLY}" for e in errors)
