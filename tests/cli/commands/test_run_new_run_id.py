"""Hidden ``sq run --run-id`` (slice 177 D4): a fresh run under a chosen id."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.cli.commands.run import _run_pipeline  # pyright: ignore[reportPrivateUsage]
from squadron.pipeline.executor import ExecutionStatus, PipelineResult
from squadron.pipeline.models import PipelineDefinition, StepConfig
from squadron.pipeline.state import RunState, StateManager

runner = CliRunner()


def _definition() -> PipelineDefinition:
    return PipelineDefinition(
        name="test-pipeline",
        description="Test pipeline",
        params={"slice": "required"},
        steps=[StepConfig(step_type="phase", name="step1", config={})],
    )


# ---------------------------------------------------------------------------
# StateManager.init_run
# ---------------------------------------------------------------------------


def test_init_run_with_a_given_id_creates_that_run(tmp_path: Path) -> None:
    manager = StateManager(runs_dir=tmp_path)

    assert manager.init_run("p4", {}, run_id="replay-1") == "replay-1"
    assert (tmp_path / "replay-1.json").is_file()


def test_init_run_with_an_existing_id_raises_and_keeps_the_file(tmp_path: Path) -> None:
    manager = StateManager(runs_dir=tmp_path)
    manager.init_run("p4", {"first": True}, run_id="replay-1")

    with pytest.raises(FileExistsError, match="replay-1"):
        manager.init_run("p4", {"second": True}, run_id="replay-1")

    state: RunState = manager.load("replay-1")
    assert state.params == {"first": True}


def test_init_run_without_an_id_mints_distinct_ids(tmp_path: Path) -> None:
    manager = StateManager(runs_dir=tmp_path)

    first = manager.init_run("p4", {})
    second = manager.init_run("p4", {})

    assert first != second and first.startswith("run-")


# ---------------------------------------------------------------------------
# _run_pipeline new_run_id
# ---------------------------------------------------------------------------


def _run(tmp_path: Path, **kwargs: object) -> None:
    result = PipelineResult(
        pipeline_name="test-pipeline", status=ExecutionStatus.COMPLETED, step_results=[]
    )
    manager = StateManager(runs_dir=tmp_path)
    with (
        patch("squadron.cli.commands.run.load_pipeline", return_value=_definition()),
        patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
        patch("squadron.cli.commands.run._check_cf"),
        patch("squadron.cli.commands.run.StateManager", return_value=manager),
        patch(
            "squadron.cli.commands.run.execute_pipeline",
            new_callable=AsyncMock,
            return_value=result,
        ),
    ):
        asyncio.run(_run_pipeline("test-pipeline", {}, runs_dir=tmp_path, **kwargs))  # type: ignore[arg-type]


def test_run_pipeline_with_new_run_id_creates_that_run_file(tmp_path: Path) -> None:
    _run(tmp_path, new_run_id="replay-9")

    assert (tmp_path / "replay-9.json").is_file()


def test_run_pipeline_with_a_taken_new_run_id_raises(tmp_path: Path) -> None:
    StateManager(runs_dir=tmp_path).init_run("test-pipeline", {}, run_id="replay-9")

    with pytest.raises(FileExistsError):
        _run(tmp_path, new_run_id="replay-9")


def test_run_pipeline_with_both_ids_raises_value_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="new_run_id and run_id"):
        _run(tmp_path, new_run_id="a", run_id="b")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_run_id_with_resume_is_a_usage_error() -> None:
    result = runner.invoke(app, ["run", "--resume", "run-1", "--run-id", "x"])

    assert result.exit_code == 1
    assert "--resume and --run-id cannot be used together" in result.output


def test_run_id_is_hidden_from_help() -> None:
    result = runner.invoke(app, ["run", "--help"])

    assert result.exit_code == 0
    assert "--run-id" not in result.output


def test_run_id_reaches_the_fresh_run() -> None:
    sdk = MagicMock()
    with (
        patch("squadron.cli.commands.run.load_pipeline", return_value=_definition()),
        patch("squadron.cli.commands.run.StateManager"),
        patch("squadron.cli.commands.run.sys") as mock_sys,
        patch("squadron.cli.commands.run._run_pipeline_sdk", sdk),
        patch("squadron.cli.commands.run.asyncio.run", side_effect=KeyboardInterrupt),
    ):
        mock_sys.stdin.isatty.return_value = False
        runner.invoke(app, ["run", "test-pipeline", "191", "--run-id", "replay-9"])

    assert sdk.call_args.kwargs["new_run_id"] == "replay-9"


def test_a_taken_run_id_exits_1_with_the_reason() -> None:
    with (
        patch("squadron.cli.commands.run.load_pipeline", return_value=_definition()),
        patch("squadron.cli.commands.run.StateManager"),
        patch("squadron.cli.commands.run._run_pipeline_sdk", MagicMock()),
        patch(
            "squadron.cli.commands.run.asyncio.run",
            side_effect=FileExistsError("run state for 'replay-9' already exists"),
        ),
    ):
        result = runner.invoke(app, ["run", "test-pipeline", "191", "--run-id", "replay-9"])

    assert result.exit_code == 1
    assert "replay-9" in result.output and "already exists" in result.output
