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


class TestDesignPlanIntegration:
    """design-plan end to end with fake actions (slice 195).

    923: design review PASS → loop skipped → PASSED.
    924: design review FAIL, both revise rounds CONCERNS → exhausted, accepted.
    928: dispatch writes no design → design step fails → FLAGGED, batch goes on.
    """

    _REVIEWS = {"923": ["PASS"], "924": ["FAIL", "CONCERNS", "CONCERNS"], "928": []}

    def _cf_client(self) -> MagicMock:
        from squadron.integrations.context_forge import ProjectInfo, SliceEntry

        def list_slices(plan: str | None = None) -> list[SliceEntry]:
            # The source reads plan 900 before any design exists; the
            # post-condition's resolve_slice_info reads the designed plan.
            return [
                SliceEntry(
                    index=int(i),
                    name=f"slice {i}",
                    design_file=None if plan == "900" else f"{i}-slice.stub.md",
                    status="not_started",
                )
                for i in self._REVIEWS
            ]

        cf_client = MagicMock()
        cf_client.list_slices.side_effect = list_slices
        cf_client.list_tasks.return_value = []
        cf_client.get_project.return_value = ProjectInfo(
            arch_file="project-documents/user/architecture/900-arch.md",
            slice_plan="900-slices.md",
            phase="4",
            slice="923",
            name="squadron",
        )
        return cf_client

    @pytest.mark.asyncio
    async def test_passed_accepted_and_flagged_slices(self, tmp_path: Path) -> None:
        from squadron.pipeline.batch_report import ItemOutcome
        from squadron.pipeline.models import ActionContext
        from squadron.pipeline.state import StateManager

        reviews = {k: list(v) for k, v in self._REVIEWS.items()}
        revise_calls: list[str] = []

        async def review_execute(ctx: ActionContext) -> ActionResult:
            verdict = reviews[str(ctx.params["slice"])].pop(0)
            return ActionResult(success=True, action_type="review", outputs={}, verdict=verdict)

        async def dispatch_execute(ctx: ActionContext) -> ActionResult:
            slice_index = str(ctx.params["slice"]) if "slice" in ctx.params else ""
            if ctx.params.get("feedback") == "review":
                revise_calls.append(str(ctx.params["slice"].get("index")))  # type: ignore[union-attr]
            elif slice_index != "928":
                (tmp_path / f"{slice_index}-slice.stub.md").write_text("# stub design")
            return ActionResult(success=True, action_type="dispatch", outputs={})

        review = MagicMock()
        review.execute = review_execute
        dispatch = MagicMock()
        dispatch.execute = dispatch_execute
        ok = _mock_action_fn(success=True)
        registry: dict[str, object] = {
            "cf-op": ok,
            "dispatch": dispatch,
            "review": review,
            "checkpoint": ok,
            "commit": ok,
        }

        run_id = StateManager(runs_dir=tmp_path).init_run("design-plan", {"plan": "900"})
        result = await execute_pipeline(
            _no_project_pipeline("design-plan"),  # type: ignore[arg-type]
            {"plan": "900", "max-revisions": "2"},
            resolver=MagicMock(),
            cf_client=self._cf_client(),
            cwd=str(tmp_path),
            run_id=run_id,
            runs_dir=tmp_path,
            _action_registry=registry,
        )

        assert result.status == ExecutionStatus.COMPLETED
        report = result.step_results[0].batch_report
        assert report is not None
        assert [(r.index, r.outcome) for r in report.records] == [
            ("923", ItemOutcome.PASSED),
            ("924", ItemOutcome.ACCEPTED),
            ("928", ItemOutcome.FLAGGED),
        ]
        assert revise_calls == ["924", "924"]
        assert all(not remaining for remaining in reviews.values())
        assert (tmp_path / f"{run_id}.slices.report.md").is_file()
