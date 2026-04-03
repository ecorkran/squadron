"""Shared fixtures for pipeline tests."""

from __future__ import annotations

import pytest

from squadron.pipeline.executor import ExecutionStatus, PipelineResult, StepResult
from squadron.pipeline.models import ActionResult
from squadron.pipeline.state import StateManager


@pytest.fixture
def state_manager(tmp_path):  # type: ignore[no-untyped-def]
    """StateManager backed by a temp directory — never touches real ~/.config."""
    return StateManager(runs_dir=tmp_path)


@pytest.fixture
def completed_pipeline_result() -> PipelineResult:
    """A PipelineResult with status=COMPLETED and one dummy StepResult."""
    step = StepResult(
        step_name="dummy-step",
        step_type="phase",
        status=ExecutionStatus.COMPLETED,
        action_results=[
            ActionResult(
                success=True,
                action_type="cf-op",
                outputs={"file": "dummy.md"},
                verdict="PASS",
            )
        ],
    )
    return PipelineResult(
        pipeline_name="dummy-pipeline",
        status=ExecutionStatus.COMPLETED,
        step_results=[step],
    )
