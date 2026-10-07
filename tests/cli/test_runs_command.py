"""sq runs list and sq runs wait (slice 199).

HOME is a per-test temp dir (tests/conftest.py), so ``StateManager()`` writes under it;
project pipelines are read from the temp cwd.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.cli.commands import runs
from squadron.pipeline.executor import ExecutionStatus
from squadron.pipeline.run_wait import WAIT_EXIT_CODES, WaitOutcome, WaitResult
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


class TestRunsWait:
    @pytest.mark.parametrize("outcome", list(WaitOutcome))
    def test_every_outcome_maps_to_its_exit_code(
        self, sm: StateManager, monkeypatch: pytest.MonkeyPatch, outcome: WaitOutcome
    ) -> None:
        run_id = begin(sm, "steps")
        end(sm, run_id, ExecutionStatus.COMPLETED)
        state = sm.load(run_id)

        def fake_wait(*_args: object, **_kwargs: object) -> WaitResult:
            return WaitResult(outcome, state)

        monkeypatch.setattr(runs, "wait_for_run", fake_wait)

        result = CliRunner().invoke(app, ["runs", "wait", run_id])

        assert result.exit_code == WAIT_EXIT_CODES[outcome]
        stderr_line = f"sq runs wait: run {run_id} {outcome}"
        assert (stderr_line in result.stderr) is (outcome is not WaitOutcome.COMPLETED)

    def test_completed_run_prints_status_and_exits_zero(self, sm: StateManager) -> None:
        run_id = begin(sm, "steps")
        end(sm, run_id, ExecutionStatus.COMPLETED)

        result = CliRunner().invoke(app, ["runs", "wait", run_id])

        assert result.exit_code == 0, result.output
        assert "Run Status" in result.stdout
        assert run_id in result.stdout

    def test_missing_run_exits_not_found(self, sm: StateManager) -> None:
        result = CliRunner().invoke(app, ["runs", "wait", "no-such-run"])

        assert result.exit_code == WAIT_EXIT_CODES[WaitOutcome.NOT_FOUND]
        assert "sq runs wait: run no-such-run not_found" in result.stderr
