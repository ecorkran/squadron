"""The loop commit ledger and its persistence (slice 202)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from squadron.pipeline.executor import ExecutionStatus, StepResult
from squadron.pipeline.loop_ledger import LoopCommitLedger
from squadron.pipeline.state import StateManager, StepState

BASE_SHA = "a" * 40
COMMIT_SHAS = ["b" * 40, "c" * 40]


def _paused_loop(ledger: LoopCommitLedger | None) -> StepResult:
    return StepResult(
        step_name="rounds",
        step_type="loop",
        status=ExecutionStatus.PAUSED,
        action_results=[],
        iteration=2,
        loop_commits=ledger,
    )


def test_ledger_round_trips_through_the_state_file(tmp_path: Path) -> None:
    manager = StateManager(runs_dir=tmp_path)
    run_id = manager.init_run("p4", {"slice": "202"})
    ledger = LoopCommitLedger(base_sha=BASE_SHA, commits=COMMIT_SHAS)

    manager.record_step_completed(run_id, _paused_loop(ledger))
    persisted = manager.load(run_id).completed_steps[0]

    assert persisted.loop_commits == ledger


def test_unprovable_flag_round_trips(tmp_path: Path) -> None:
    manager = StateManager(runs_dir=tmp_path)
    run_id = manager.init_run("p4", {"slice": "202"})
    ledger = LoopCommitLedger(base_sha=BASE_SHA, commits=[], unprovable=True)

    manager.record_step_completed(run_id, _paused_loop(ledger))

    assert manager.load(run_id).completed_steps[0].loop_commits == ledger


def test_step_without_a_ledger_persists_none(tmp_path: Path) -> None:
    manager = StateManager(runs_dir=tmp_path)
    run_id = manager.init_run("p4", {"slice": "202"})

    manager.record_step_completed(run_id, _paused_loop(None))

    assert manager.load(run_id).completed_steps[0].loop_commits is None


def test_state_file_written_without_loop_commits_still_loads() -> None:
    older = {
        "step_name": "rounds",
        "step_type": "loop",
        "status": "paused",
        "action_results": [],
        "iteration": 2,
        "completed_at": datetime.now(UTC).isoformat(),
    }

    assert StepState.model_validate(older).loop_commits is None
