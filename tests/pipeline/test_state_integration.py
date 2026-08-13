"""Integration tests for StateManager + execute_pipeline.

Verifies that the state manager correctly persists and resumes pipeline runs
using the real executor (with mocked actions).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
from squadron.pipeline.loader import load_pipeline
from squadron.pipeline.models import ActionResult
from squadron.pipeline.state import StateManager
from tests.pipeline.conftest import artifact_writing_action, phase_artifact_cf_client


def _no_project_pipeline(name: str) -> object:
    """Load a built-in pipeline, bypassing project/user dirs."""
    return load_pipeline(
        name,
        project_dir=Path("/nonexistent"),
        user_dir=Path("/nonexistent"),
    )


def _mock_action(success: bool = True, verdict: str | None = None) -> MagicMock:
    result = ActionResult(
        success=success,
        action_type="mock",
        outputs={},
        verdict=verdict,
    )
    action = MagicMock()
    action.execute = AsyncMock(return_value=result)
    return action


def _success_registry(dispatch_action: MagicMock | None = None) -> dict[str, object]:
    """Registry where all actions return success."""
    action = _mock_action(success=True)
    return {
        "cf-op": action,
        "dispatch": dispatch_action or action,
        "review": _mock_action(success=True, verdict="PASS"),
        "checkpoint": _mock_action(success=True),
        "commit": action,
        "compact": action,
        "summary": action,
        "devlog": action,
    }


def _paused_checkpoint_registry(
    pause_on_step: int = 2, dispatch_action: MagicMock | None = None
) -> dict[str, object]:
    """Registry where the checkpoint action pauses on the Nth call."""
    call_count = [0]
    normal_action = _mock_action(success=True)
    review_action = _mock_action(success=True, verdict="PASS")

    paused_result = ActionResult(
        success=True,
        action_type="checkpoint",
        outputs={"checkpoint": "paused"},
        verdict="CONCERNS",
    )
    normal_checkpoint = ActionResult(
        success=True,
        action_type="checkpoint",
        outputs={},
    )

    checkpoint_mock = MagicMock()

    async def checkpoint_execute(ctx: object) -> ActionResult:
        call_count[0] += 1
        if call_count[0] >= pause_on_step:
            return paused_result
        return normal_checkpoint

    checkpoint_mock.execute = checkpoint_execute

    return {
        "cf-op": normal_action,
        "dispatch": dispatch_action or normal_action,
        "review": review_action,
        "checkpoint": checkpoint_mock,
        "commit": normal_action,
        "summary": normal_action,
        "devlog": normal_action,
    }


class TestStateIntegration:
    @pytest.mark.asyncio
    async def test_full_run_state_reflects_all_steps(self, tmp_path: Path) -> None:
        """Full run through slice populates state with all 5 steps."""
        definition = _no_project_pipeline("slice")
        mgr = StateManager(runs_dir=tmp_path)
        run_id = mgr.init_run("slice", {"slice": "191"})
        cf_client = phase_artifact_cf_client(191, "191-slice.stub.md", "191-tasks.stub.md")
        dispatch_action = artifact_writing_action(tmp_path, 191)

        result = await execute_pipeline(
            definition,
            {"slice": "191"},
            resolver=MagicMock(),
            cf_client=cf_client,
            cwd=str(tmp_path),
            run_id=run_id,
            on_step_complete=mgr.make_step_callback(run_id),
            runs_dir=tmp_path,
            _action_registry=_success_registry(dispatch_action=dispatch_action),
        )
        mgr.finalize(run_id, result)

        state = mgr.load(run_id)
        assert state.status == "completed"
        assert len(state.completed_steps) == 10
        step_names = [s.step_name for s in state.completed_steps]
        assert any("design" in n for n in step_names)
        assert any("devlog" in n for n in step_names)

    @pytest.mark.asyncio
    async def test_resume_from_paused_completes_all_steps(self, tmp_path: Path) -> None:
        """A paused run can be resumed; final state has all 5 steps completed."""
        definition = _no_project_pipeline("slice")
        mgr = StateManager(runs_dir=tmp_path)
        run_id = mgr.init_run("slice", {"slice": "191"})
        cf_client = phase_artifact_cf_client(191, "191-slice.stub.md", "191-tasks.stub.md")
        dispatch_action = artifact_writing_action(tmp_path, 191)

        # First execution — checkpoint pauses at 2nd checkpoint call (tasks step)
        result1 = await execute_pipeline(
            definition,
            {"slice": "191"},
            resolver=MagicMock(),
            cf_client=cf_client,
            cwd=str(tmp_path),
            run_id=run_id,
            on_step_complete=mgr.make_step_callback(run_id),
            runs_dir=tmp_path,
            _action_registry=_paused_checkpoint_registry(
                pause_on_step=2, dispatch_action=dispatch_action
            ),
        )
        # Must have paused
        assert result1.status == ExecutionStatus.PAUSED

        state = mgr.load(run_id)
        assert state.status == "paused"

        # Verify resume inputs
        start_from = mgr.first_unfinished_step(run_id, definition)
        assert start_from is not None
        prior_outputs = mgr.load_prior_outputs(run_id)

        # Second execution — resume from paused step, all actions succeed
        result2 = await execute_pipeline(
            definition,
            {"slice": "191"},
            resolver=MagicMock(),
            cf_client=cf_client,
            cwd=str(tmp_path),
            run_id=run_id,
            start_from=start_from,
            on_step_complete=mgr.make_step_callback(run_id),
            runs_dir=tmp_path,
            _action_registry=_success_registry(dispatch_action=dispatch_action),
        )
        mgr.finalize(run_id, result2)

        final = mgr.load(run_id)
        assert final.status == "completed"
        # 10 top-level steps, but the paused step ("tasks") is recorded twice:
        # once as PAUSED, once as COMPLETED on resume (slice 915 Part A —
        # first_unfinished_step now returns to the paused step and it
        # re-executes, rather than being skipped as already-done).
        assert len(final.completed_steps) == 11
        _ = prior_outputs  # consumed by executor internally
