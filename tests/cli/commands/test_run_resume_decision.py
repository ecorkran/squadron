"""Plain ``sq run --resume`` with ``--decision`` / ``--instructions`` (#246)."""

from __future__ import annotations

from pathlib import Path

import pytest
import typer

from squadron.cli.commands.run import _resume_params  # pyright: ignore[reportPrivateUsage]
from squadron.cli.commands.run_item import USAGE_EXIT
from squadron.pipeline.batch_report import ItemDecision
from squadron.pipeline.control_params import ACCEPT_DECISION, OVERRIDE_INSTRUCTIONS
from squadron.pipeline.models import PipelineDefinition, StepConfig
from squadron.pipeline.state import RunState, StateManager


def _definition() -> PipelineDefinition:
    return PipelineDefinition(
        name="p6",
        description="t",
        params={},
        steps=[
            StepConfig(step_type="implement", name="implement", config={}),
            StepConfig(step_type="loop", name="revise-code", config={}),
        ],
    )


def _state(tmp_path: Path) -> RunState:
    sm = StateManager(runs_dir=tmp_path / "runs")
    return sm.load(sm.init_run("p6", {"slice": "105"}))


def test_no_decision_keeps_the_run_params(tmp_path: Path) -> None:
    params = _resume_params(_state(tmp_path), _definition(), "revise-code", None, None)
    assert params == {"slice": "105"}


def test_retry_is_the_plain_resume(tmp_path: Path) -> None:
    params = _resume_params(_state(tmp_path), _definition(), "revise-code", ItemDecision.RETRY, None)
    assert ACCEPT_DECISION not in params


def test_accept_at_a_loop_sets_the_accept_decision(tmp_path: Path) -> None:
    params = _resume_params(_state(tmp_path), _definition(), "revise-code", ItemDecision.ACCEPT, None)
    assert params[ACCEPT_DECISION] is True


def test_accept_at_a_non_loop_step_is_a_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(typer.Exit) as exit_info:
        _resume_params(_state(tmp_path), _definition(), "implement", ItemDecision.ACCEPT, None)

    assert exit_info.value.exit_code == USAGE_EXIT
    assert "needs a run paused at a loop step" in " ".join(capsys.readouterr().err.split())


def test_instructions_reach_the_dispatches(tmp_path: Path) -> None:
    params = _resume_params(_state(tmp_path), _definition(), "revise-code", None, "fix the tests")
    assert params[OVERRIDE_INSTRUCTIONS] == "fix the tests"
