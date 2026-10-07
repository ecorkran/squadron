"""Reserved control param keys (slice 197 D8, D9; criterion 16, 17)."""

from __future__ import annotations

import click
import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.pipeline.loader import validate_pipeline
from squadron.pipeline.models import PipelineDefinition, StepConfig

runner = CliRunner()


@pytest.mark.parametrize(
    ("key", "message"),
    [
        ("accept_decision", "'accept_decision' is reserved; use --decision accept"),
        ("override_instructions", "'override_instructions' is reserved; use --instructions"),
    ],
)
def test_a_reserved_p_key_is_rejected_before_anything_runs(key: str, message: str) -> None:
    result = runner.invoke(app, ["run", "P6", "105", "-p", f"{key}=x", "--model", "haiku"])

    assert result.exit_code == 2
    # Typer forces colour when GITHUB_ACTIONS is set, so strip styling before matching.
    assert message in " ".join(click.unstyle(result.output).split())


@pytest.mark.parametrize("key", ["accept_decision", "override_instructions"])
def test_a_reserved_key_in_a_pipeline_params_block_is_rejected(key: str) -> None:
    definition = PipelineDefinition(
        name="p",
        description="",
        params={"slice": "required", key: "x"},
        steps=[StepConfig(step_type="devlog", name="devlog-0", config={"mode": "auto"})],
    )

    errors = validate_pipeline(definition)

    assert [(e.field, e.message) for e in errors if e.field.startswith("params.")] == [
        (
            f"params.{key}",
            f"'{key}' is reserved; use "
            + ("--decision accept" if key == "accept_decision" else "--instructions"),
        )
    ]
