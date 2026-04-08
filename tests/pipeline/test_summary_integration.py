"""Integration tests for slice 161: summary step through execute_pipeline (T14)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
from squadron.pipeline.models import ActionResult, PipelineDefinition, StepConfig
from squadron.pipeline.state import StateManager


def _make_definition(steps: list[StepConfig]) -> PipelineDefinition:
    return PipelineDefinition(
        name="test-summary",
        description="",
        model=None,
        params={},
        steps=steps,
    )


def _make_session(capture_return: str = "SUMMARY TEXT") -> MagicMock:
    session = MagicMock()
    session.current_model = "claude-sonnet-4-6"
    session.capture_summary = AsyncMock(return_value=capture_return)
    session.compact = AsyncMock()
    session.set_model = AsyncMock()
    session.connect = AsyncMock()
    session.disconnect = AsyncMock()
    session.seed_context = AsyncMock()
    return session


def _make_resolver() -> MagicMock:
    resolver = MagicMock()
    resolver.resolve.return_value = ("claude-haiku-4-5-20251001", None)
    return resolver


class TestSummaryStep:
    """End-to-end: summary step runs through execute_pipeline."""

    @pytest.mark.asyncio
    async def test_stdout_emit_does_not_rotate_session(self) -> None:
        """Summary with stdout emit: captures summary once, does not rotate."""
        definition = _make_definition(
            [
                StepConfig(
                    step_type="summary",
                    name="s",
                    config={"template": "minimal-sdk", "emit": ["stdout"]},
                )
            ]
        )
        session = _make_session("MY SUMMARY")
        result = await execute_pipeline(
            definition,
            {},
            resolver=_make_resolver(),
            cf_client=MagicMock(),
            sdk_session=session,
        )
        assert result.status == ExecutionStatus.COMPLETED
        # capture_summary was called once (summary dispatched)
        session.capture_summary.assert_awaited_once()
        # compact (rotate) must NOT have been called
        session.compact.assert_not_called()
        # the summary text is in the action outputs
        outputs = result.step_results[0].action_results[0].outputs
        assert outputs["summary"] == "MY SUMMARY"

    @pytest.mark.asyncio
    async def test_file_emit_writes_to_file(self, tmp_path: Path) -> None:
        """Summary with file emit writes to specified path relative to cwd."""
        definition = _make_definition(
            [
                StepConfig(
                    step_type="summary",
                    name="s",
                    config={
                        "template": "minimal-sdk",
                        "emit": [{"file": "out.md"}],
                    },
                )
            ]
        )
        session = _make_session("FILE SUMMARY")
        result = await execute_pipeline(
            definition,
            {},
            resolver=_make_resolver(),
            cf_client=MagicMock(),
            sdk_session=session,
            cwd=str(tmp_path),
        )
        assert result.status == ExecutionStatus.COMPLETED
        assert (tmp_path / "out.md").read_text() == "FILE SUMMARY"

    @pytest.mark.asyncio
    async def test_rotate_emit_calls_compact_with_summary(self) -> None:
        """Summary with rotate emit: compact called once with captured summary."""
        definition = _make_definition(
            [
                StepConfig(
                    step_type="summary",
                    name="s",
                    config={"template": "minimal-sdk", "emit": ["rotate"]},
                )
            ]
        )
        session = _make_session("ROTATE SUMMARY")
        result = await execute_pipeline(
            definition,
            {},
            resolver=_make_resolver(),
            cf_client=MagicMock(),
            sdk_session=session,
        )
        assert result.status == ExecutionStatus.COMPLETED
        session.compact.assert_awaited_once()
        rot_kwargs = session.compact.await_args.kwargs
        assert rot_kwargs["summary"] == "ROTATE SUMMARY"

    @pytest.mark.asyncio
    async def test_checkpoint_shorthand_pauses_pipeline(self) -> None:
        """Summary with checkpoint:always causes PAUSED status."""
        definition = _make_definition(
            [
                StepConfig(
                    step_type="summary",
                    name="s",
                    config={
                        "template": "minimal-sdk",
                        "emit": ["stdout"],
                        "checkpoint": "always",
                    },
                )
            ]
        )
        session = _make_session()
        result = await execute_pipeline(
            definition,
            {},
            resolver=_make_resolver(),
            cf_client=MagicMock(),
            sdk_session=session,
        )
        assert result.status == ExecutionStatus.PAUSED

    @pytest.mark.asyncio
    async def test_no_sdk_session_fails_summary_step(self) -> None:
        """Summary step without SDK session → FAILED with descriptive error."""
        definition = _make_definition(
            [
                StepConfig(
                    step_type="summary",
                    name="s",
                    config={"template": "minimal-sdk", "emit": ["rotate"]},
                )
            ]
        )
        result = await execute_pipeline(
            definition,
            {},
            resolver=_make_resolver(),
            cf_client=MagicMock(),
            sdk_session=None,
        )
        assert result.status == ExecutionStatus.FAILED
        failed = result.step_results[0]
        # Error is in the action result, not propagated to StepResult.error
        assert len(failed.action_results) >= 1
        action_error = failed.action_results[0].error
        assert action_error is not None
        assert "SDK" in action_error

    def test_compact_alias_state_callback_still_fires(self, tmp_path: Path) -> None:
        """Regression: compact step (T10 refactor) still records compact_summaries.

        Exercises _maybe_record_compact_summaries() directly with an ActionResult
        shaped exactly like what the refactored CompactAction produces.
        """
        mgr = StateManager(runs_dir=tmp_path)
        run_id = mgr.init_run("test-pipeline", {"slice": "154"})
        cb = mgr.make_step_callback(run_id)

        # Outputs produced by refactored CompactAction via _execute_summary
        ar = ActionResult(
            success=True,
            action_type="compact",
            outputs={
                "summary": "COMPACT SUMMARY",
                "instructions": "compact instructions",
                "source_step_index": 0,
                "source_step_name": "compact-step",
                "summary_model": "haiku-id",
                "emit_results": [
                    {"destination": "rotate", "ok": True, "detail": "session rotated"}
                ],
            },
        )
        from squadron.pipeline.executor import ExecutionStatus, StepResult

        cb(
            StepResult(
                step_name="compact-step",
                step_type="compact",
                status=ExecutionStatus.COMPLETED,
                action_results=[ar],
            )
        )

        state = mgr.load(run_id)
        assert "0:compact-step" in state.compact_summaries
        cs = state.compact_summaries["0:compact-step"]
        assert cs.text == "COMPACT SUMMARY"
        assert cs.summary_model == "haiku-id"
