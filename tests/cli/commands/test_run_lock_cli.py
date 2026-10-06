"""`sq run` holds the project run lock for mutating pipelines (slice 197 D11, criteria 15, 17)."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.pipeline.executor import ExecutionStatus, PipelineResult
from squadron.pipeline.loader import load_pipeline
from squadron.pipeline.models import PipelineDefinition, StepConfig
from squadron.pipeline.run_lock import pipeline_mutates, project_run_lock
from squadron.pipeline.state import ExecutionMode

runner = CliRunner()


@pytest.mark.parametrize("name", ["implement-plan", "slices-plan", "tasks-plan", "P6"])
def test_code_and_batch_pipelines_mutate(name: str) -> None:
    assert pipeline_mutates(load_pipeline(name)) is True


def test_review_and_summary_pipelines_do_not_mutate() -> None:
    summary_only = PipelineDefinition(
        name="s",
        description="",
        params={},
        steps=[StepConfig(step_type="summary", name="summary-0", config={"template": "minimal"})],
    )
    assert pipeline_mutates(load_pipeline("review")) is False
    assert pipeline_mutates(summary_only) is False


def test_a_loop_that_commits_each_round_mutates() -> None:
    definition = PipelineDefinition(
        name="l",
        description="",
        params={},
        steps=[
            StepConfig(
                step_type="loop",
                name="loop-0",
                config={"max": 2, "commit_each_iteration": True, "steps": [{"review": {}}]},
            )
        ],
    )
    assert pipeline_mutates(definition) is True


@pytest.fixture
def in_repo(temp_git_repo: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(temp_git_repo)
    return temp_git_repo


@pytest.fixture
def runner_spy() -> Iterator[MagicMock]:
    """``asyncio.run`` in run.py, so a test can see whether anything ran."""
    done = PipelineResult(pipeline_name="p6", status=ExecutionStatus.COMPLETED, step_results=[])
    with patch("squadron.cli.commands.run.asyncio") as mock_asyncio:
        mock_asyncio.run.side_effect = lambda coro: (coro.close(), done)[1]
        yield mock_asyncio.run


def _fresh_p6() -> object:
    with patch("squadron.cli.commands.run.sys") as mock_sys:
        mock_sys.stdin.isatty.return_value = False
        return runner.invoke(app, ["run", "P6", "105", "--model", "haiku"])


def test_a_fresh_run_takes_the_lock_and_runs(in_repo: Path, runner_spy: MagicMock) -> None:
    result = _fresh_p6()

    assert result.exit_code == 0  # type: ignore[attr-defined]
    runner_spy.assert_called_once()
    assert (in_repo / ".git" / "squadron-run.flock").exists()


def test_a_held_lock_exits_2_and_runs_nothing(
    in_repo: Path, runner_spy: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.ERROR)
    with project_run_lock(str(in_repo)):
        result = _fresh_p6()

    assert result.exit_code == 2  # type: ignore[attr-defined]
    assert "another squadron run holds the project lock" in " ".join(
        result.output.split()  # type: ignore[attr-defined]
    )
    runner_spy.assert_not_called()


def test_a_failed_git_dir_read_exits_2_and_runs_nothing(in_repo: Path, runner_spy: MagicMock) -> None:
    with patch("squadron.pipeline.run_lock.run_git", return_value=None):
        result = _fresh_p6()

    assert result.exit_code == 2  # type: ignore[attr-defined]
    runner_spy.assert_not_called()


def test_an_unopenable_lock_file_exits_2_and_runs_nothing(in_repo: Path, runner_spy: MagicMock) -> None:
    with patch(
        "squadron.pipeline.run_lock.Path.open", side_effect=PermissionError(13, "Permission denied")
    ):
        result = _fresh_p6()

    assert result.exit_code == 2  # type: ignore[attr-defined]
    runner_spy.assert_not_called()


def test_a_plain_resume_of_a_paused_run_with_the_lock_held_exits_2(
    in_repo: Path, runner_spy: MagicMock
) -> None:
    state = MagicMock()
    state.pipeline = "P6"
    state.params = {"slice": "105", "model": "haiku"}
    state.execution_mode = ExecutionMode.SDK
    state_mgr = MagicMock()
    state_mgr.load.return_value = state
    state_mgr.first_unfinished_step.return_value = "implement-1"
    state_mgr.load_iteration.return_value = 0

    with (
        patch("squadron.cli.commands.run.StateManager", return_value=state_mgr),
        patch("squadron.cli.commands.run._resolve_resume_iteration", return_value=0),
        project_run_lock(str(in_repo)),
    ):
        result = runner.invoke(app, ["run", "--resume", "abc123"])

    assert result.exit_code == 2
    runner_spy.assert_not_called()
