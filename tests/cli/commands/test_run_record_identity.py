"""A new run is recorded under the pipeline's identity and, for a path run, its file (D4)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from squadron.cli.commands.run import _handle_prompt_only_init, _run_pipeline
from squadron.pipeline.executor import ExecutionStatus, PipelineResult
from squadron.pipeline.models import PipelineDefinition, StepConfig
from squadron.pipeline.state import StateManager


def _definition(name: str) -> PipelineDefinition:
    return PipelineDefinition(
        name=name,
        description="Test pipeline",
        params={},
        steps=[StepConfig(step_type="phase", name="step1", config={})],
    )


def _start_sdk_run(arg: str, runs_dir: Path) -> StateManager:
    """Start a fresh SDK run for *arg* with execution and cf stubbed out."""
    result = PipelineResult(pipeline_name="x", status=ExecutionStatus.COMPLETED, step_results=[])
    manager = StateManager(runs_dir=runs_dir)
    with (
        patch("squadron.cli.commands.run.load_pipeline", return_value=_definition("x")),
        patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
        patch("squadron.cli.commands.run._check_cf"),
        patch(
            "squadron.cli.commands.run.execute_pipeline", new_callable=AsyncMock, return_value=result
        ),
        patch("squadron.cli.commands.run.StateManager", return_value=manager),
    ):
        asyncio.run(_run_pipeline(arg, {}, runs_dir=runs_dir))
    return manager


def test_path_run_records_identity_and_absolute_path(tmp_path: Path) -> None:
    source = tmp_path / "x" / "Foo.yaml"
    source.parent.mkdir()
    source.write_text("name: foo\n", encoding="utf-8")
    runs_dir = tmp_path / "runs"

    manager = _start_sdk_run(str(source), runs_dir)

    (run,) = manager.list_runs()
    assert run.pipeline == "foo"
    assert run.pipeline_path == str(source.resolve())
    assert [r.run_id for r in manager.list_runs(pipeline="foo")] == [run.run_id]


def test_named_run_records_no_path(tmp_path: Path) -> None:
    manager = _start_sdk_run("slices-plan", tmp_path / "runs")

    (run,) = manager.list_runs()
    assert run.pipeline == "slices-plan"
    assert run.pipeline_path is None


def test_prompt_only_path_run_records_identity_and_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "Bar.yaml"
    source.write_text("name: bar\n", encoding="utf-8")
    manager = StateManager(runs_dir=tmp_path / "runs")

    with (
        patch("squadron.cli.commands.run.load_pipeline", return_value=_definition("bar")),
        patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
        patch("squadron.cli.commands.run.render_step_instructions") as render,
        patch("squadron.cli.commands.run.StateManager", return_value=manager),
    ):
        render.return_value.to_json.return_value = "{}"
        _handle_prompt_only_init(str(source), None, None, None)

    (run,) = manager.list_runs()
    assert run.pipeline == "bar"
    assert run.pipeline_path == str(source.resolve())


@pytest.mark.parametrize(
    ("flag", "handler"),
    [("--prompt-only", "_handle_prompt_only_init"), ("--explain", "_handle_explain")],
)
def test_path_argument_keeps_its_case_on_every_entry_point(
    tmp_path: Path, flag: str, handler: str
) -> None:
    from typer.testing import CliRunner

    from squadron.cli.app import app

    source = tmp_path / "X" / "Foo.yaml"
    source.parent.mkdir()
    source.write_text("name: foo\n", encoding="utf-8")

    with patch(f"squadron.cli.commands.run.{handler}") as called:
        CliRunner().invoke(app, ["run", str(source), flag])

    assert called.call_args.args[0] == str(source)


@pytest.mark.parametrize("flag", ["--prompt-only", "--explain"])
def test_name_argument_is_lowercased_on_every_entry_point(flag: str) -> None:
    from typer.testing import CliRunner

    from squadron.cli.app import app

    handler = "_handle_prompt_only_init" if flag == "--prompt-only" else "_handle_explain"
    with patch(f"squadron.cli.commands.run.{handler}") as called:
        CliRunner().invoke(app, ["run", "Slices-Plan", flag])

    assert called.call_args.args[0] == "slices-plan"
