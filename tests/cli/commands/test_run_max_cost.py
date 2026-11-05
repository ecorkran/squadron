"""``sq run --max-cost`` (#241): a per-run dollar cap kept in the run's params."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.pipeline.control_params import RUN_MAX_COST
from squadron.pipeline.loader import load_pipeline
from squadron.pipeline.models import PipelineDefinition, StepConfig
from squadron.pipeline.state import RunState

runner = CliRunner()


def _definition() -> PipelineDefinition:
    return PipelineDefinition(
        name="test-pipeline",
        description="Test pipeline",
        params={"slice": "required"},
        steps=[StepConfig(step_type="phase", name="step1", config={})],
    )


def _fresh_run_params(*args: str) -> dict[str, object]:
    sdk = MagicMock()
    with (
        patch("squadron.cli.commands.run.load_pipeline", return_value=_definition()),
        patch("squadron.cli.commands.run.StateManager"),
        patch("squadron.cli.commands.run.sys") as mock_sys,
        patch("squadron.cli.commands.run._run_pipeline_sdk", sdk),
        patch("squadron.cli.commands.run.asyncio.run", side_effect=KeyboardInterrupt),
    ):
        mock_sys.stdin.isatty.return_value = False
        runner.invoke(app, ["run", "test-pipeline", "191", *args])
    return sdk.call_args.args[1]


def test_max_cost_reaches_the_fresh_run_params() -> None:
    assert _fresh_run_params("--max-cost", "2.5")[RUN_MAX_COST] == 2.5


def test_without_max_cost_the_params_carry_no_cap() -> None:
    assert RUN_MAX_COST not in _fresh_run_params()


@pytest.mark.parametrize("raw", ["0", "-1", "inf", "nan"])
def test_a_non_positive_or_non_finite_max_cost_is_a_usage_error(raw: str) -> None:
    sdk = MagicMock()
    with patch("squadron.cli.commands.run._run_pipeline_sdk", sdk):
        result = runner.invoke(app, ["run", "test-pipeline", "191", "--max-cost", raw])

    assert result.exit_code == 2
    sdk.assert_not_called()


def test_max_cost_with_prompt_only_is_refused() -> None:
    result = runner.invoke(app, ["run", "test-pipeline", "191", "--prompt-only", "--max-cost", "1"])

    assert result.exit_code == 1
    assert "--max-cost cannot be combined with --prompt-only" in result.output


def test_max_cost_cannot_be_set_through_a_param() -> None:
    with patch("squadron.cli.commands.run.load_pipeline", return_value=_definition()):
        result = runner.invoke(app, ["run", "test-pipeline", "191", "-p", f"{RUN_MAX_COST}=9"])

    assert result.exit_code != 0
    assert "--max-cost" in result.output


def test_resume_max_cost_replaces_the_stored_cap() -> None:
    state = MagicMock(spec=RunState)
    state.params = {"slice": "191", RUN_MAX_COST: 1.0}
    state.execution_mode = "sdk"
    state.load_target = "test-pipeline"
    sdk = MagicMock()
    with (
        patch("squadron.cli.commands.run.StateManager") as manager_cls,
        patch("squadron.cli.commands.run._refuse_live_run"),
        patch("squadron.cli.commands.run._load_run_definition", return_value=_definition()),
        patch("squadron.cli.commands.run._resolve_resume_iteration", return_value=0),
        patch("squadron.cli.commands.run._run_pipeline_sdk", sdk),
        patch("squadron.cli.commands.run.asyncio.run", side_effect=KeyboardInterrupt),
    ):
        manager_cls.return_value.load.return_value = state
        manager_cls.return_value.first_unfinished_step.return_value = "step1"
        runner.invoke(app, ["run", "--resume", "run-1", "--max-cost", "4"])

    assert sdk.call_args.args[1][RUN_MAX_COST] == 4.0


def test_pipeline_yaml_max_cost_usd_loads(tmp_path: Path) -> None:
    pipeline = tmp_path / "capped.yaml"
    pipeline.write_text(
        "name: capped\nmax_cost_usd: 3\nsteps:\n  - dispatch: { prompt: hi, model: sonnet }\n"
    )

    assert load_pipeline(str(pipeline)).max_cost_usd == 3.0


def test_pipeline_yaml_non_positive_max_cost_usd_is_rejected(tmp_path: Path) -> None:
    pipeline = tmp_path / "capped.yaml"
    pipeline.write_text(
        "name: capped\nmax_cost_usd: 0\nsteps:\n  - dispatch: { prompt: hi, model: sonnet }\n"
    )

    with pytest.raises(ValueError, match="max_cost_usd"):
        load_pipeline(str(pipeline))
