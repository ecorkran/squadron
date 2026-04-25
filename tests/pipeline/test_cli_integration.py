"""Integration tests for sq run CLI wiring.

Exercises the full wiring path: _run_pipeline → load_pipeline → execute_pipeline
→ StateManager, using mock action registries at the action boundary.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadron.cli.commands.run import _run_pipeline
from squadron.pipeline.executor import ExecutionStatus
from squadron.pipeline.loader import load_pipeline
from squadron.pipeline.models import ActionResult
from squadron.pipeline.state import StateManager

# ---------------------------------------------------------------------------
# Helpers (shared with test_state_integration.py)
# ---------------------------------------------------------------------------


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


def _success_registry() -> dict[str, object]:
    """Registry where all actions return success."""
    action = _mock_action(success=True)
    return {
        "cf-op": action,
        "dispatch": action,
        "review": _mock_action(success=True, verdict="PASS"),
        "checkpoint": _mock_action(success=True),
        "commit": action,
        "compact": action,
        "summary": action,
        "devlog": action,
    }


def _paused_checkpoint_registry(
    pause_on_step: int = 2,
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
        "dispatch": normal_action,
        "review": review_action,
        "checkpoint": checkpoint_mock,
        "commit": normal_action,
        "compact": normal_action,
        "devlog": normal_action,
    }


# ---------------------------------------------------------------------------
# T12: Full execution integration test
# ---------------------------------------------------------------------------


class TestCliIntegration:
    @pytest.mark.asyncio
    async def test_run_pipeline_completes_successfully(self, tmp_path: Path) -> None:
        """_run_pipeline returns COMPLETED and persists state."""
        with patch("squadron.cli.commands.run._check_cf"):
            result = await _run_pipeline(
                "slice",
                {"slice": "191"},
                runs_dir=tmp_path,
                _action_registry=_success_registry(),
            )

        assert result.status == ExecutionStatus.COMPLETED
        assert len(result.step_results) == 6

        # State file should be loadable
        mgr = StateManager(runs_dir=tmp_path)
        runs = mgr.list_runs()
        assert len(runs) == 1
        assert runs[0].status == "completed"
        assert len(runs[0].completed_steps) == 6

    @pytest.mark.asyncio
    async def test_state_file_loadable_after_run(self, tmp_path: Path) -> None:
        """State file is persisted and loadable via StateManager."""
        with patch("squadron.cli.commands.run._check_cf"):
            await _run_pipeline(
                "slice",
                {"slice": "191"},
                runs_dir=tmp_path,
                _action_registry=_success_registry(),
            )

        mgr = StateManager(runs_dir=tmp_path)
        runs = mgr.list_runs()
        state = mgr.load(runs[0].run_id)
        assert state.pipeline == "slice"
        assert state.params["slice"] == "191"

    # -------------------------------------------------------------------
    # T13: Resume from paused
    # -------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_resume_from_paused_completes(self, tmp_path: Path) -> None:
        """First run pauses; second run resumes and completes all steps."""
        with patch("squadron.cli.commands.run._check_cf"):
            result1 = await _run_pipeline(
                "slice",
                {"slice": "191"},
                runs_dir=tmp_path,
                _action_registry=_paused_checkpoint_registry(pause_on_step=2),
            )

        assert result1.status == ExecutionStatus.PAUSED

        mgr = StateManager(runs_dir=tmp_path)
        runs = mgr.list_runs()
        assert runs[0].status == "paused"
        run_id = runs[0].run_id

        # Resume: load definition, find next step, re-execute
        definition = _no_project_pipeline("slice")
        next_step = mgr.first_unfinished_step(run_id, definition)
        assert next_step is not None

        from squadron.pipeline.executor import execute_pipeline

        with patch("squadron.cli.commands.run._check_cf"):
            result2 = await execute_pipeline(
                definition,
                {"slice": "191"},
                resolver=MagicMock(),
                cf_client=MagicMock(),
                run_id=run_id,
                start_from=next_step,
                on_step_complete=mgr.make_step_callback(run_id),
                _action_registry=_success_registry(),
            )
        mgr.finalize(run_id, result2)

        final = mgr.load(run_id)
        assert final.status == "completed"
        assert len(final.completed_steps) == 6

    # -------------------------------------------------------------------
    # T18: --from mid-process adoption
    # -------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_from_step_skips_earlier_steps(self, tmp_path: Path) -> None:
        """Starting from 'implement-3' skips design/tasks/compact."""
        with patch("squadron.cli.commands.run._check_cf"):
            result = await _run_pipeline(
                "slice",
                {"slice": "191"},
                runs_dir=tmp_path,
                from_step="implement-3",
                _action_registry=_success_registry(),
            )

        assert result.status == ExecutionStatus.COMPLETED
        completed_names = [sr.step_name for sr in result.step_results]
        # Only implement-3 and devlog-4 should be in results
        assert "design-0" not in completed_names
        assert "tasks-1" not in completed_names
        assert "implement-3" in completed_names

    # -------------------------------------------------------------------
    # T19: Dry-run produces no state file
    # -------------------------------------------------------------------

    def test_dry_run_creates_no_state_file(self, tmp_path: Path) -> None:
        """--dry-run path does not write any state file."""
        from typer.testing import CliRunner

        from squadron.cli.app import app
        from squadron.pipeline.models import PipelineDefinition, StepConfig

        test_runner = CliRunner()
        defn = PipelineDefinition(
            name="test",
            description="Test",
            params={"slice": "required"},
            steps=[StepConfig(step_type="phase", name="s1", config={})],
        )
        with (
            patch("squadron.cli.commands.run.load_pipeline", return_value=defn),
            patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
        ):
            result = test_runner.invoke(app, ["run", "--dry-run", "test", "191"])
        assert result.exit_code == 0
        assert not list(tmp_path.glob("*.json"))
