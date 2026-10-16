"""Loop rounds through the run-state round-trip (slice 176 D3)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from squadron.pipeline.executor import ExecutionStatus, StepResult
from squadron.pipeline.models import ActionResult
from squadron.pipeline.state import StateManager, StepState


def _review(verdict: str) -> ActionResult:
    return ActionResult(
        success=True, action_type="review", outputs={"verdict": verdict}, verdict=verdict
    )


def _loop_step(rounds: list[list[ActionResult]], final: list[ActionResult]) -> StepResult:
    return StepResult(
        step_name="rounds",
        step_type="loop",
        status=ExecutionStatus.COMPLETED,
        action_results=final,
        prior_rounds=rounds,
        accepted=True,
        exhausted=True,
        iteration=len(rounds) + 1,
    )


def test_prior_rounds_round_trip_in_order(tmp_path: Path) -> None:
    manager = StateManager(runs_dir=tmp_path)
    run_id = manager.init_run("p4", {"slice": "176"})
    step = _loop_step([[_review("FAIL")], [_review("CONCERNS")]], [_review("PASS")])

    manager.record_step_completed(run_id, step)
    persisted = manager.load(run_id).completed_steps[0]

    verdicts = [
        [action["verdict"] for action in round_results]
        for round_results in persisted.prior_round_results
    ]
    assert verdicts == [["FAIL"], ["CONCERNS"]]
    assert persisted.accepted is True
    assert persisted.exhausted is True
    assert [action["verdict"] for action in persisted.action_results] == ["PASS"]


def test_non_loop_step_writes_empty_round_fields(tmp_path: Path) -> None:
    manager = StateManager(runs_dir=tmp_path)
    run_id = manager.init_run("p4", {"slice": "176"})
    step = StepResult(
        step_name="design",
        step_type="phase",
        status=ExecutionStatus.COMPLETED,
        action_results=[_review("PASS")],
    )

    manager.record_step_completed(run_id, step)
    persisted = manager.load(run_id).completed_steps[0]

    assert persisted.prior_round_results == []
    assert persisted.accepted is False
    assert persisted.exhausted is False


def test_step_state_without_round_keys_loads_with_defaults() -> None:
    older = {
        "step_name": "rounds",
        "step_type": "loop",
        "status": "completed",
        "action_results": [],
        "iteration": 2,
        "completed_at": datetime.now(UTC).isoformat(),
    }

    loaded = StepState.model_validate(older)

    assert loaded.prior_round_results == []
    assert loaded.accepted is False
    assert loaded.exhausted is False


def test_verdict_hoist_ignores_earlier_rounds(tmp_path: Path) -> None:
    manager = StateManager(runs_dir=tmp_path)
    run_id = manager.init_run("p4", {"slice": "176"})
    step = _loop_step([[_review("FAIL")], [_review("CONCERNS")]], [_review("PASS")])

    manager.record_step_completed(run_id, step)

    assert manager.load(run_id).completed_steps[0].verdict == "PASS"
