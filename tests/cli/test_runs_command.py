"""sq runs list and sq runs wait (slice 199).

HOME is a per-test temp dir (tests/conftest.py), so ``StateManager()`` writes under it;
project pipelines are read from the temp cwd.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.pipeline.executor import ExecutionStatus
from squadron.pipeline.state import StateManager
from tests.pipeline.run_listing_support import (
    STEP_NAMES,
    begin,
    completed_batch_run,
    end,
    pause_at,
    write_batch_pipeline,
    write_step_pipeline,
)


@pytest.fixture
def sm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> StateManager:
    monkeypatch.chdir(tmp_path)
    pipelines = tmp_path / "project-documents/user/pipelines"
    write_step_pipeline(pipelines, "steps")
    write_batch_pipeline(pipelines, "batch")
    return StateManager()


def _invoke(*args: str) -> str:
    result = CliRunner().invoke(app, ["runs", *args])
    assert result.exit_code == 0, result.output
    return " ".join(result.output.split())


class TestRunsList:
    def test_shows_resumable_runs(self, sm: StateManager) -> None:
        paused = begin(sm, "steps")
        pause_at(sm, paused, STEP_NAMES[1], done=[STEP_NAMES[0]])
        batch = completed_batch_run(sm, "batch")

        out = _invoke("list")

        assert paused in out and STEP_NAMES[1] in out
        assert batch in out and "3 items in slices (1 accept)" in out
        assert "Resume a step:" in out

    def test_empty_result_exits_zero(self, sm: StateManager) -> None:
        assert "No resumable runs. Use --all to include completed runs." in _invoke("list")

    def test_all_includes_completed_and_running(self, sm: StateManager) -> None:
        running = begin(sm, "steps")
        done = begin(sm, "steps")
        end(sm, done, ExecutionStatus.COMPLETED)

        assert running not in _invoke("list")
        out = _invoke("list", "--all")
        assert running in out and done in out

    def test_pipeline_filter(self, sm: StateManager) -> None:
        paused = begin(sm, "steps")
        pause_at(sm, paused, STEP_NAMES[0])
        batch = completed_batch_run(sm, "batch")

        out = _invoke("list", "--pipeline", "BATCH")

        assert batch in out
        assert paused not in out

    def test_bare_group_prints_help(self) -> None:
        result = CliRunner().invoke(app, ["runs"])
        assert "list" in result.output
