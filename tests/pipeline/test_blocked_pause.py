"""A BLOCKED marker after implement pauses the run; resuming re-runs implement (slice 947 D7/D8)."""

from __future__ import annotations

from collections.abc import Iterator
from itertools import count
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadron.pipeline.executor import ExecutionStatus, PipelineResult, execute_pipeline
from squadron.pipeline.models import ActionResult, PipelineDefinition, StepConfig
from squadron.pipeline.state import StateManager
from squadron.pipeline.steps import register_step_type
from tests.pipeline.conftest import phase_artifact_cf_client

SLICE = 107
TASK_FILE = "107-tasks.stub.md"
BLOCKED_LINE = "> BLOCKED: no judge-template review artifact ... PM asked"
_names = count()


@pytest.fixture(autouse=True)
def implement_dispatch_left_no_blocked_markers() -> None:
    """Override the suite-wide stub: the real task-file reading runs here."""


@pytest.fixture(autouse=True)
def implement_dispatch_left_commits() -> Iterator[None]:
    """The agent that is blocked wrote no code: branch-work counts no commits."""
    with patch(
        "squadron.events.builtin.dispatch_branch_work.DispatchBranchWorkAction._count_work",
        return_value=("107-slice.stub", 0, "main"),
    ):
        yield


def _write_tasks(repo: Path, text: str) -> None:
    path = repo / "project-documents/user/tasks" / TASK_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _pipeline() -> PipelineDefinition:
    """An implement step followed by a step that must not run while the run is paused."""
    after_kind = f"_blocked_after_{next(_names)}"
    after_type = MagicMock()
    after_type.expand.return_value = [("after", {})]
    register_step_type(after_kind, after_type)
    definition = PipelineDefinition(
        name="p6",
        description="test",
        params={},
        steps=[
            StepConfig(
                step_type="implement",
                name="implement-0",
                config={"phase": 6, "slice": str(SLICE), "model": "opus"},
            ),
            StepConfig(step_type=after_kind, name="after-0", config={}),
        ],
    )
    return definition


def _action(action_type: str) -> MagicMock:
    impl = MagicMock()
    impl.execute = AsyncMock(
        side_effect=lambda ctx: ActionResult(
            success=True, action_type=action_type, outputs={"response": "stopped, asked the PM"}
        )
    )
    return impl


async def _run(
    tmp_path: Path,
    definition: PipelineDefinition,
    actions: dict[str, MagicMock],
    run_id: str,
    start_from: str | None = None,
) -> PipelineResult:
    return await execute_pipeline(
        definition,
        {"_project": "test"},
        resolver=MagicMock(),
        cf_client=phase_artifact_cf_client(SLICE, f"{SLICE}-slice.stub.md", TASK_FILE),
        cwd=str(tmp_path),
        run_id=run_id,
        runs_dir=tmp_path / "runs",
        start_from=start_from,
        _action_registry={**actions},
    )


def _actions() -> dict[str, MagicMock]:
    return {name: _action(name) for name in ("cf-op", "dispatch", "commit", "after")}


@pytest.mark.asyncio
async def test_blocked_marker_with_no_commits_pauses_at_implement(tmp_path: Path) -> None:
    _write_tasks(tmp_path, f"- [ ] 7.2 Capture the artifact\n  {BLOCKED_LINE}\n")
    run_id = StateManager(runs_dir=tmp_path / "runs").init_run("p6", {})
    actions = _actions()

    result = await _run(tmp_path, _pipeline(), actions, run_id)

    assert result.status is ExecutionStatus.PAUSED
    assert result.paused_at == "implement-0"
    paused = result.step_results[0].action_results[-1]
    assert paused.awaits_human
    assert paused.error is not None
    assert "no judge-template review artifact ... PM asked" in paused.error
    assert f"sq run --resume {run_id}" in paused.error
    actions["after"].execute.assert_not_awaited()  # nothing after implement ran


@pytest.mark.asyncio
async def test_resume_after_a_blocked_pause_redispatches_implement(tmp_path: Path) -> None:
    _write_tasks(tmp_path, f"- [ ] 7.2 Capture the artifact\n  {BLOCKED_LINE}\n")
    run_id = StateManager(runs_dir=tmp_path / "runs").init_run("p6", {})
    actions = _actions()
    definition = _pipeline()
    paused = await _run(tmp_path, definition, actions, run_id)
    assert paused.status is ExecutionStatus.PAUSED
    assert actions["dispatch"].execute.await_count == 1

    # The Project Manager resolves the blocker and removes the marker line.
    _write_tasks(tmp_path, "- [x] 7.2 Capture the artifact\n")
    with patch(
        "squadron.events.builtin.dispatch_branch_work.DispatchBranchWorkAction._count_work",
        return_value=("107-slice.stub", 2, "main"),
    ):
        resumed = await _run(tmp_path, definition, actions, run_id, start_from=paused.paused_at)

    assert resumed.status is ExecutionStatus.COMPLETED
    assert actions["dispatch"].execute.await_count == 2  # implement ran again
    actions["after"].execute.assert_awaited_once()
