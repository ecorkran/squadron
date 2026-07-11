"""Integration tests for the pipeline executor.

Loads real built-in pipeline definitions and runs them with mocked actions.
Real CF client is not required.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadron.pipeline.executor import ExecutionStatus, StepResult, execute_pipeline
from squadron.pipeline.loader import load_pipeline
from squadron.pipeline.models import ActionResult
from tests.pipeline.conftest import artifact_writing_action, phase_artifact_cf_client


def _mock_action_fn(success: bool = True, verdict: str | None = None) -> MagicMock:
    """Build an async mock action that always returns the given result."""
    result = ActionResult(
        success=success,
        action_type="mock",
        outputs={},
        verdict=verdict,
    )
    action = MagicMock()
    action.execute = AsyncMock(return_value=result)
    return action


def _no_project_pipeline(name: str) -> object:
    """Load a built-in pipeline, bypassing project/user dirs."""
    return load_pipeline(
        name,
        project_dir=Path("/nonexistent"),
        user_dir=Path("/nonexistent"),
    )


def _success_registry() -> dict[str, object]:
    """Action registry where every action returns success."""
    action = _mock_action_fn(success=True)
    return {
        "cf-op": action,
        "dispatch": action,
        "review": _mock_action_fn(success=True, verdict="PASS"),
        "checkpoint": _mock_action_fn(success=True),
        "commit": action,
        "compact": action,
        "summary": action,
        "devlog": action,
    }


def _artifact_writing_success_registry(cwd: Path, slice_index: int) -> dict[str, object]:
    """Success registry whose dispatch mock writes the expected phase artifact.

    Mirrors _success_registry but the "dispatch" action writes to whichever
    path the current call's params/expected kind requires, satisfying the
    dispatch artifact post-condition for design/tasks phase steps.
    """
    action = _mock_action_fn(success=True)
    return {
        "cf-op": action,
        "dispatch": artifact_writing_action(cwd, slice_index),
        "review": _mock_action_fn(success=True, verdict="PASS"),
        "checkpoint": _mock_action_fn(success=True),
        "commit": action,
        "compact": action,
        "summary": action,
        "devlog": action,
    }


class TestSliceLifecycleIntegration:
    @pytest.mark.asyncio
    async def test_all_steps_completed(self, tmp_path: Path) -> None:
        from squadron.pipeline.state import StateManager

        definition = _no_project_pipeline("slice")
        registry = _artifact_writing_success_registry(tmp_path, 149)
        cf_client = phase_artifact_cf_client(149, "149-slice.stub.md", "149-tasks.stub.md")
        state_mgr = StateManager(runs_dir=tmp_path)
        run_id = state_mgr.init_run("slice", {"slice": "149"})

        result = await execute_pipeline(
            definition,
            {"slice": "149"},
            resolver=MagicMock(),
            cf_client=cf_client,
            cwd=str(tmp_path),
            run_id=run_id,
            runs_dir=tmp_path,
            _action_registry=registry,
        )

        assert result.status == ExecutionStatus.COMPLETED
        assert len(result.step_results) == 10
        assert all(sr.status == ExecutionStatus.COMPLETED for sr in result.step_results)

    @pytest.mark.asyncio
    async def test_on_step_complete_called_in_order(self, tmp_path: Path) -> None:
        from squadron.pipeline.state import StateManager

        definition = _no_project_pipeline("slice")
        registry = _artifact_writing_success_registry(tmp_path, 149)
        cf_client = phase_artifact_cf_client(149, "149-slice.stub.md", "149-tasks.stub.md")
        state_mgr = StateManager(runs_dir=tmp_path)
        run_id = state_mgr.init_run("slice", {"slice": "149"})
        received: list[StepResult] = []

        await execute_pipeline(
            definition,
            {"slice": "149"},
            resolver=MagicMock(),
            cf_client=cf_client,
            cwd=str(tmp_path),
            run_id=run_id,
            runs_dir=tmp_path,
            on_step_complete=received.append,
            _action_registry=registry,
        )

        assert len(received) == 10
        step_names = [sr.step_name for sr in received]
        assert step_names[0].startswith("design")
        assert step_names[-1].startswith("devlog")

    @pytest.mark.asyncio
    async def test_start_from_compact_skips_earlier_steps(self) -> None:
        definition = _no_project_pipeline("slice")
        registry = _success_registry()

        # compact-3 is the fourth step (0-indexed)
        result = await execute_pipeline(
            definition,
            {"slice": "149"},
            resolver=MagicMock(),
            cf_client=MagicMock(),
            start_from="compact-3",
            _action_registry=registry,
        )

        assert result.status == ExecutionStatus.COMPLETED
        # Should have 7 steps: compact-3, summary-4, implement-5, summary-6,
        # compact-7, summary-8, devlog-9
        assert len(result.step_results) == 7
        assert result.step_results[0].step_name == "compact-3"

    @pytest.mark.asyncio
    async def test_missing_required_param_slice(self) -> None:
        definition = _no_project_pipeline("slice")

        with pytest.raises(ValueError, match="slice"):
            await execute_pipeline(
                definition,
                {},  # missing required "slice"
                resolver=MagicMock(),
                cf_client=MagicMock(),
                _action_registry={},
            )


class TestReviewOnlyIntegration:
    @pytest.mark.asyncio
    async def test_completed_with_pass_verdict(self) -> None:
        definition = _no_project_pipeline("review")
        registry = _success_registry()

        result = await execute_pipeline(
            definition,
            {"slice": "149", "template": "arch"},
            resolver=MagicMock(),
            cf_client=MagicMock(),
            _action_registry=registry,
        )

        assert result.status == ExecutionStatus.COMPLETED


class TestDesignBatchIntegration:
    @pytest.mark.asyncio
    async def test_two_slices_inner_steps_run_twice(self, tmp_path: Path) -> None:
        from squadron.integrations.context_forge import ProjectInfo, SliceEntry, TaskEntry
        from squadron.pipeline.state import StateManager

        definition = _no_project_pipeline("design-batch")

        cf_client = MagicMock()
        cf_client.list_slices.return_value = [
            SliceEntry(index=10, name="sl-a", design_file="10-slice.sl-a.md", status="not_started"),
            SliceEntry(index=11, name="sl-b", design_file="11-slice.sl-b.md", status="in_progress"),
        ]
        cf_client.list_tasks.return_value = [
            TaskEntry(index=10, files=[]),
            TaskEntry(index=11, files=[]),
        ]
        cf_client.get_project.return_value = ProjectInfo(
            arch_file="project-documents/user/architecture/100-arch.md",
            slice_plan="100-slices.md",
            phase="4",
            slice="10",
            name="squadron",
        )

        call_count = 0

        async def counting_execute(ctx: object) -> ActionResult:
            nonlocal call_count
            call_count += 1
            return ActionResult(
                success=True,
                action_type="mock",
                outputs={},
                verdict="PASS",
            )

        async def dispatch_execute(ctx: object) -> ActionResult:
            nonlocal call_count
            call_count += 1
            slice_index = ctx.params["slice"]  # type: ignore[attr-defined]
            suffix = "a" if str(slice_index) == "10" else "b"
            design_path = tmp_path / f"{slice_index}-slice.sl-{suffix}.md"
            design_path.write_text("# stub design")
            return ActionResult(success=True, action_type="dispatch", outputs={})

        action = MagicMock()
        action.execute = counting_execute
        dispatch_mock = MagicMock()
        dispatch_mock.execute = dispatch_execute
        registry: dict[str, object] = {
            "cf-op": action,
            "dispatch": dispatch_mock,
            "review": action,
            "checkpoint": action,
            "commit": action,
        }

        state_mgr = StateManager(runs_dir=tmp_path)
        run_id = state_mgr.init_run("design-batch", {"plan": "my-plan"})

        result = await execute_pipeline(
            definition,
            {"plan": "my-plan"},
            resolver=MagicMock(),
            cf_client=cf_client,
            cwd=str(tmp_path),
            run_id=run_id,
            runs_dir=tmp_path,
            _action_registry=registry,
        )

        assert result.status == ExecutionStatus.COMPLETED
        # design step expands to: cf-op(set_phase), cf-op(set_slice), cf-op(build),
        # dispatch, review, checkpoint, commit = 7 actions × 2 slices = 14 total calls
        assert call_count == 14
