"""Shared fixtures for pipeline tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from squadron.pipeline.executor import ExecutionStatus, PipelineResult, StepResult
from squadron.pipeline.models import ActionResult
from squadron.pipeline.state import StateManager


@pytest.fixture
def state_manager(tmp_path):  # type: ignore[no-untyped-def]
    """StateManager backed by a temp directory — never touches real ~/.config."""
    return StateManager(runs_dir=tmp_path)


def phase_artifact_cf_client(slice_index: int, design_file: str, task_file: str) -> MagicMock:
    """A CF client mock that resolves a slice with real design/task filenames.

    Needed because design/tasks steps (PhaseStepType) require
    resolve_slice_info() to succeed and their dispatch to write the resolved
    artifact — see the dispatch artifact post-condition (issue #15).
    """
    from squadron.integrations.context_forge import ProjectInfo, SliceEntry, TaskEntry

    cf_client = MagicMock()
    cf_client.list_slices.return_value = [
        SliceEntry(index=slice_index, name="stub", design_file=design_file, status="in_progress"),
    ]
    cf_client.list_tasks.return_value = [
        TaskEntry(index=slice_index, files=[task_file]),
    ]
    cf_client.get_project.return_value = ProjectInfo(
        arch_file="project-documents/user/architecture/100-arch.md",
        slice_plan="100-slices.md",
        phase="4",
        slice=str(slice_index),
        name="squadron",
    )
    return cf_client


def artifact_writing_action(cwd: Path, slice_index: int) -> MagicMock:
    """A dispatch-style mock action that writes the expected phase artifact.

    Paths must match phase_artifact_cf_client's design_file/task_file:
    the design path is used verbatim (no prefix); the task path gets the
    project-documents/user/tasks/ prefix applied by resolve_slice_info.
    """
    design_path = cwd / f"{slice_index}-slice.stub.md"
    task_path = cwd / f"project-documents/user/tasks/{slice_index}-tasks.stub.md"

    async def dispatch_execute(ctx: object) -> ActionResult:
        design_path.write_text("# stub design")
        task_path.parent.mkdir(parents=True, exist_ok=True)
        task_path.write_text("# stub tasks")
        return ActionResult(success=True, action_type="dispatch", outputs={})

    dispatch_mock = MagicMock()
    dispatch_mock.execute = dispatch_execute
    return dispatch_mock


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
