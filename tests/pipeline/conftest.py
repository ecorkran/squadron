"""Shared fixtures for pipeline tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from squadron.pipeline.executor import ExecutionStatus, PipelineResult, StepResult
from squadron.pipeline.loader import load_pipeline
from squadron.pipeline.models import ActionResult, PipelineDefinition
from squadron.pipeline.state import StateManager

# Test-only pipelines; kept out of the shipped data/pipelines directory.
FIXTURE_PIPELINES_DIR = Path(__file__).parent / "fixtures" / "pipelines"


def load_fixture_pipeline(name: str) -> PipelineDefinition:
    """Load a test-only pipeline from FIXTURE_PIPELINES_DIR by its file stem."""
    return load_pipeline(str(FIXTURE_PIPELINES_DIR / f"{name}.yaml"))


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


# ---------------------------------------------------------------------------
# SDK session fakes (slice 932)
# ---------------------------------------------------------------------------


def sdk_text(text: str, *, parent_tool_use_id: str | None = None) -> object:
    """A real AssistantMessage carrying one text block; a parent id marks a subagent's."""
    from claude_agent_sdk import AssistantMessage, TextBlock

    return AssistantMessage(
        content=[TextBlock(text=text)], model="test-model", parent_tool_use_id=parent_tool_use_id
    )


def sdk_result(text: str = "", *, injected: bool = False) -> object:
    """A real ResultMessage; ``injected`` marks a task-notification turn."""
    from claude_agent_sdk import ResultMessage

    return ResultMessage(
        subtype="success",
        duration_ms=1,
        duration_api_ms=1,
        is_error=False,
        num_turns=1,
        session_id="sess-1",
        result=text,
        origin={"kind": "task-notification"} if injected else None,
    )


def sdk_task_started(task_id: str, task_type: str, description: str = "") -> object:
    from claude_agent_sdk import TaskStartedMessage

    return TaskStartedMessage(
        subtype="task_started",
        data={},
        task_id=task_id,
        description=description or f"task {task_id}",
        uuid=f"u-{task_id}",
        session_id="sess-1",
        task_type=task_type,
    )


def sdk_task_notification(task_id: str) -> object:
    from claude_agent_sdk import TaskNotificationMessage

    return TaskNotificationMessage(
        subtype="task_notification",
        data={},
        task_id=task_id,
        status="completed",
        output_file="",
        summary="done",
        uuid=f"n-{task_id}",
        session_id="sess-1",
    )


def sdk_task_updated(task_id: str, status: str) -> object:
    from claude_agent_sdk import TaskUpdatedMessage

    return TaskUpdatedMessage(
        subtype="task_updated",
        data={},
        task_id=task_id,
        patch={},
        status=status,  # type: ignore[arg-type]
    )


class ScriptedClient:
    """Fake ClaudeSDKClient: each receive_response() call plays the next script.

    A script item that is a float sleeps that many seconds before the next
    message (to exercise timeouts). Calls past the last script yield nothing.
    """

    def __init__(self, *scripts: list[object], connect_error: Exception | None = None) -> None:
        from unittest.mock import AsyncMock

        self._scripts = list(scripts)
        self.receive_calls = 0
        self.connect = AsyncMock(side_effect=connect_error)
        self.disconnect = AsyncMock()
        self.set_model = AsyncMock()
        self.query = AsyncMock()
        self.stop_task = AsyncMock()

    async def _play(self, script: list[object]):  # type: ignore[no-untyped-def]
        import asyncio

        for item in script:
            if isinstance(item, float):
                await asyncio.sleep(item)
                continue
            yield item

    def receive_response(self):  # type: ignore[no-untyped-def]
        index = self.receive_calls
        self.receive_calls += 1
        script = self._scripts[index] if index < len(self._scripts) else []
        return self._play(script)


def scripted_session(client: ScriptedClient) -> object:
    """A real SDKExecutionSession around a scripted client."""
    from claude_agent_sdk import ClaudeAgentOptions

    from squadron.pipeline.sdk_session import SDKExecutionSession

    return SDKExecutionSession(
        client=client,  # type: ignore[arg-type]
        base_options=ClaudeAgentOptions(cwd=".", permission_mode="bypassPermissions"),
    )


def failing_reconnect_patch(error_text: str = "spawn failed: E2BIG") -> object:
    """Patch so the next rotation's fresh client fails to connect."""
    from unittest.mock import patch

    from claude_agent_sdk import CLIConnectionError

    fresh = ScriptedClient(connect_error=CLIConnectionError(error_text))
    return patch("squadron.pipeline.sdk_session.ClaudeSDKClient", return_value=fresh)


def typed_config(values: dict[str, object]) -> object:
    """A ``get_typed_config`` stand-in answering per key; unlisted keys raise."""

    def _get(key: str, type_: type, cwd: str = ".") -> object:
        if key not in values:
            raise AssertionError(f"unexpected config read: {key}")
        return values[key]

    return _get
