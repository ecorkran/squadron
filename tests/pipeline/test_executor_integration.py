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


class TestSliceLifecycleIntegration:
    @pytest.mark.asyncio
    async def test_all_steps_completed(self) -> None:
        definition = _no_project_pipeline("slice")
        registry = _success_registry()

        result = await execute_pipeline(
            definition,
            {"slice": "149"},
            resolver=MagicMock(),
            cf_client=MagicMock(),
            _action_registry=registry,
        )

        assert result.status == ExecutionStatus.COMPLETED
        assert len(result.step_results) == 10
        assert all(sr.status == ExecutionStatus.COMPLETED for sr in result.step_results)

    @pytest.mark.asyncio
    async def test_on_step_complete_called_in_order(self) -> None:
        definition = _no_project_pipeline("slice")
        registry = _success_registry()
        received: list[StepResult] = []

        await execute_pipeline(
            definition,
            {"slice": "149"},
            resolver=MagicMock(),
            cf_client=MagicMock(),
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
    async def test_two_slices_inner_steps_run_twice(self) -> None:
        from squadron.integrations.context_forge import SliceEntry

        definition = _no_project_pipeline("design-batch")

        cf_client = MagicMock()
        cf_client.list_slices.return_value = [
            SliceEntry(index=10, name="sl-a", design_file=None, status="not_started"),
            SliceEntry(index=11, name="sl-b", design_file=None, status="in_progress"),
        ]

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

        action = MagicMock()
        action.execute = counting_execute
        registry: dict[str, object] = {
            "cf-op": action,
            "dispatch": action,
            "review": action,
            "checkpoint": action,
            "commit": action,
        }

        result = await execute_pipeline(
            definition,
            {"plan": "my-plan"},
            resolver=MagicMock(),
            cf_client=cf_client,
            _action_registry=registry,
        )

        assert result.status == ExecutionStatus.COMPLETED
        # design step expands to: cf-op(set_phase), cf-op(set_slice), cf-op(build),
        # dispatch, review, checkpoint, commit = 7 actions × 2 slices = 14 total calls
        assert call_count == 14
