"""Integration tests for the pipeline executor.

Loads real built-in pipeline definitions and runs them with mocked actions.
Real CF client is not required.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
from squadron.pipeline.loader import load_pipeline
from squadron.pipeline.models import ActionResult
from tests.pipeline.conftest import (
    artifact_writing_action,
    load_fixture_pipeline,
    phase_artifact_cf_client,
)
from tests.pipeline.observer_support import RecordingObserver


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


def _success_registry() -> dict[str, object]:
    """Action registry where every action returns success."""
    action = _mock_action_fn(success=True)
    return {
        "cf-op": action,
        "branch": action,
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
        "branch": action,
        "dispatch": artifact_writing_action(cwd, slice_index),
        "review": _mock_action_fn(success=True, verdict="PASS"),
        "checkpoint": _mock_action_fn(success=True),
        "commit": action,
        "compact": action,
        "summary": action,
        "devlog": action,
    }


_NONEXISTENT = Path("/nonexistent")


class TestSliceLifecycleIntegration:
    @pytest.mark.asyncio
    async def test_all_steps_completed(self, tmp_path: Path) -> None:
        from squadron.pipeline.state import StateManager

        definition = load_fixture_pipeline("slice")
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
        assert len(result.step_results) == 12
        assert all(sr.status == ExecutionStatus.COMPLETED for sr in result.step_results)

    @pytest.mark.asyncio
    async def test_observer_step_completed_in_order(self, tmp_path: Path) -> None:
        from squadron.pipeline.state import StateManager

        definition = load_fixture_pipeline("slice")
        registry = _artifact_writing_success_registry(tmp_path, 149)
        cf_client = phase_artifact_cf_client(149, "149-slice.stub.md", "149-tasks.stub.md")
        state_mgr = StateManager(runs_dir=tmp_path)
        run_id = state_mgr.init_run("slice", {"slice": "149"})
        observer = RecordingObserver()

        await execute_pipeline(
            definition,
            {"slice": "149"},
            resolver=MagicMock(),
            cf_client=cf_client,
            cwd=str(tmp_path),
            run_id=run_id,
            runs_dir=tmp_path,
            observer=observer,
            _action_registry=registry,
        )

        assert len(observer.completed) == 12
        step_names = [sr.step_name for sr in observer.completed]
        assert step_names[0].startswith("design")
        assert step_names[-1].startswith("branch")
        assert step_names[-2].startswith("devlog")

    @pytest.mark.asyncio
    async def test_start_from_compact_skips_earlier_steps(self) -> None:
        definition = load_fixture_pipeline("slice")
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
        # Should have 9 steps: compact-3, summary-4, branch-5, implement-6, summary-7,
        # compact-8, summary-9, devlog-10, branch-11
        assert len(result.step_results) == 9
        assert result.step_results[0].step_name == "compact-3"

    @pytest.mark.asyncio
    async def test_missing_required_param_slice(self) -> None:
        definition = load_fixture_pipeline("slice")

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
        definition = load_pipeline("review", project_dir=_NONEXISTENT, user_dir=_NONEXISTENT)
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
    """slices-plan end to end with fake actions (slice 195).

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

        # The item-reset summary step (#148): one per item, before its design.
        resets: list[str] = []

        async def summary_execute(ctx: ActionContext) -> ActionResult:
            resets.append(str(ctx.params["template"]))
            return ActionResult(success=True, action_type="summary", outputs={})

        review = MagicMock()
        review.execute = review_execute
        dispatch = MagicMock()
        dispatch.execute = dispatch_execute
        summary = MagicMock()
        summary.execute = summary_execute
        ok = _mock_action_fn(success=True)
        registry: dict[str, object] = {
            "cf-op": ok,
            "branch": ok,
            "dispatch": dispatch,
            "review": review,
            "summary": summary,
            "checkpoint": ok,
            "commit": ok,
        }

        run_id = StateManager(runs_dir=tmp_path).init_run("slices-plan", {"plan": "900"})
        result = await execute_pipeline(
            load_pipeline("slices-plan", project_dir=_NONEXISTENT, user_dir=_NONEXISTENT),  # type: ignore[arg-type]
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
        # Every item resets, including the flagged one.
        assert resets == ["item-reset"] * 3
        assert all(not remaining for remaining in reviews.values())
        assert (tmp_path / f"{run_id}.slices.report.md").is_file()
