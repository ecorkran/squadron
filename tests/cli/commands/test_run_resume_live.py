"""--resume refuses a run still owned by a live process and takes over an orphaned one (#195)."""

from __future__ import annotations

from pathlib import Path

import pytest
import typer

from squadron.cli.commands.run import _refuse_live_run  # pyright: ignore[reportPrivateUsage]
from squadron.pipeline.executor import ExecutionStatus, PipelineResult
from squadron.pipeline.state import RunOwner, StateManager
from tests.pipeline.liveness_support import exited_pid


@pytest.fixture
def manager(tmp_path: Path) -> StateManager:
    return StateManager(runs_dir=tmp_path)


def test_a_live_run_exits_1_naming_its_owner(
    manager: StateManager, capsys: pytest.CaptureFixture[str]
) -> None:
    owner = RunOwner.current(30)
    state = manager.load(manager.init_run("p", {}, owner=owner))

    with pytest.raises(typer.Exit) as exc_info:
        _refuse_live_run(state)

    assert exc_info.value.exit_code == 1
    assert f"still running under pid {owner.pid}" in capsys.readouterr().out


def test_an_orphaned_run_resumes(manager: StateManager) -> None:
    dead = RunOwner.current(30).model_copy(update={"pid": exited_pid()})
    state = manager.load(manager.init_run("p", {}, owner=dead))

    _refuse_live_run(state)


def test_a_failed_run_resumes(manager: StateManager) -> None:
    run_id = manager.init_run("p", {}, owner=RunOwner.current(30))
    failed = PipelineResult(pipeline_name="p", status=ExecutionStatus.FAILED, step_results=[])
    manager.finalize(run_id, failed)

    _refuse_live_run(manager.load(run_id))
