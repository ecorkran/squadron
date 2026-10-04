"""`existing: keep` on design and tasks steps (slice 196 D11)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadron.documents.frontmatter import read_frontmatter
from squadron.events import EventType
from squadron.events.builtin.dispatch_artifact import DispatchArtifactAction
from squadron.events.builtin.revision_stamp import RevisionStampAction
from squadron.events.contexts import PostActionContext
from squadron.integrations.context_forge import ProjectInfo, SliceEntry, TaskEntry
from squadron.pipeline.actions.dispatch import DispatchAction
from squadron.pipeline.models import ActionContext, ActionResult, StepConfig
from squadron.pipeline.steps.phase import ArtifactKind, ExistingArtifactPolicy, PhaseStepType

SLICE = 105
DESIGN = "project-documents/user/slices/105-slice.stub.md"
TASKS = "project-documents/user/tasks/105-tasks.stub.md"
_P = "squadron.pipeline.actions.dispatch"


def _step(config: dict[str, object]) -> StepConfig:
    return StepConfig(step_type="tasks", name="tasks-0", config=config)


# ---------------------------------------------------------------------------
# Step validation and expansion
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("policy", ["create", "keep"])
def test_valid_policies_pass_validation(policy: str) -> None:
    errors = PhaseStepType("tasks").validate(_step({"phase": 5, "slice": "1", "existing": policy}))
    assert errors == []


def test_unknown_policy_is_rejected() -> None:
    errors = PhaseStepType("tasks").validate(_step({"phase": 5, "existing": "overwrite"}))

    assert [e.field for e in errors] == ["existing"]
    assert "'overwrite' is not a valid 'existing' policy" in errors[0].message


def test_keep_on_implement_is_rejected() -> None:
    step = StepConfig(step_type="implement", name="i", config={"phase": 6, "existing": "keep"})
    errors = PhaseStepType("implement").validate(step)
    assert [e.field for e in errors] == ["existing"]


def test_keep_on_an_initiative_scoped_step_is_rejected() -> None:
    errors = PhaseStepType("design").validate(
        StepConfig(step_type="design", name="d", config={"phase": 2, "plan": "1", "existing": "keep"})
    )
    assert [e.field for e in errors] == ["existing"]


def test_keep_travels_to_the_dispatch_config_with_the_artifact_kind() -> None:
    actions = PhaseStepType("tasks").expand(_step({"phase": 5, "existing": "keep"}))

    dispatch = next(cfg for kind, cfg in actions if kind == "dispatch")
    assert dispatch["existing"] == ExistingArtifactPolicy.KEEP
    assert dispatch["artifact_kind"] == ArtifactKind.TASKS


@pytest.mark.parametrize("config", [{"phase": 5}, {"phase": 5, "existing": "create"}])
def test_default_and_create_leave_the_dispatch_config_unchanged(config: dict[str, object]) -> None:
    actions = PhaseStepType("tasks").expand(_step(config))

    dispatch = next(cfg for kind, cfg in actions if kind == "dispatch")
    assert "existing" not in dispatch and "artifact_kind" not in dispatch


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def _cf() -> MagicMock:
    client = MagicMock()
    client.list_slices.return_value = [
        SliceEntry(index=SLICE, name="Stub", design_file=DESIGN, status="in_progress")
    ]
    client.list_tasks.return_value = [TaskEntry(index=SLICE, files=["105-tasks.stub.md"])]
    client.get_project.return_value = ProjectInfo(
        arch_file="a.md", slice_plan="p", phase="Phase 5", slice=str(SLICE), name="squadron"
    )
    return client


def _dispatch_context(cwd: Path, **extra: object) -> ActionContext:
    params: dict[str, object] = {"prompt": "go", "slice": str(SLICE), **extra}
    return ActionContext(
        pipeline_name="p",
        run_id="r",
        params=params,
        step_name="tasks-0",
        step_index=0,
        prior_outputs={},
        resolver=MagicMock(),
        cf_client=_cf(),
        cwd=str(cwd),
    )


_KEEP: dict[str, object] = {
    "existing": ExistingArtifactPolicy.KEEP,
    "artifact_kind": ArtifactKind.TASKS,
}


def _write_tasks(cwd: Path) -> None:
    path = cwd / TASKS
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\ndocType: tasks\n---\n# tasks\n")


@pytest.mark.asyncio
async def test_keep_with_an_existing_artifact_makes_no_model_call(tmp_path: Path) -> None:
    _write_tasks(tmp_path)
    context = _dispatch_context(tmp_path, **_KEEP)

    with (
        patch.object(DispatchAction, "_dispatch_via_agent", new_callable=AsyncMock) as agent,
        patch.object(DispatchAction, "_dispatch_via_session", new_callable=AsyncMock) as session,
    ):
        result = await DispatchAction().execute(context)

    assert result.success is True
    assert result.outputs == {"skipped": "artifact exists", "paths": [TASKS]}
    agent.assert_not_called()
    session.assert_not_called()
    context.resolver.resolve.assert_not_called()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_keep_with_no_artifact_dispatches_normally(tmp_path: Path) -> None:
    context = _dispatch_context(tmp_path, **_KEEP)
    normal = ActionResult(success=True, action_type="dispatch", outputs={"response": "written"})
    context.resolver.resolve.return_value = ("m", "openai")  # type: ignore[attr-defined]

    with patch.object(
        DispatchAction, "_dispatch_via_agent", new_callable=AsyncMock, return_value=normal
    ) as agent:
        result = await DispatchAction().execute(context)

    agent.assert_awaited_once()
    assert result.outputs == {"response": "written"}


@pytest.mark.asyncio
async def test_default_create_dispatches_even_when_the_artifact_exists(tmp_path: Path) -> None:
    _write_tasks(tmp_path)
    context = _dispatch_context(tmp_path)  # no existing/artifact_kind params
    normal = ActionResult(success=True, action_type="dispatch", outputs={"response": "written"})
    context.resolver.resolve.return_value = ("m", "openai")  # type: ignore[attr-defined]

    with patch.object(
        DispatchAction, "_dispatch_via_agent", new_callable=AsyncMock, return_value=normal
    ) as agent:
        await DispatchAction().execute(context)

    agent.assert_awaited_once()


# ---------------------------------------------------------------------------
# Post-condition and revision stamp
# ---------------------------------------------------------------------------


def _post_action(cwd: Path, outputs: dict[str, object], iteration: int = 1) -> PostActionContext:
    return PostActionContext(
        event=EventType.POST_ACTION,
        cwd=str(cwd),
        params={"slice": str(SLICE)},
        action_type="dispatch",
        result=ActionResult(success=True, action_type="dispatch", outputs=outputs),
        run_id="r",
        run_started_at=datetime.now(UTC),  # after the artifact was written
        run_state_error=None,
        step_name="tasks-0",
        step_type="tasks",
        expected_artifact_kind=ArtifactKind.TASKS,
        iteration=iteration,
        cf_client=_cf(),
    )


_SKIPPED: dict[str, object] = {"skipped": "artifact exists", "paths": [TASKS]}


@pytest.mark.asyncio
async def test_post_condition_is_satisfied_by_a_kept_artifact(tmp_path: Path) -> None:
    _write_tasks(tmp_path)  # written BEFORE the run started, so a normal check would fail

    result = await DispatchArtifactAction().execute(_post_action(tmp_path, _SKIPPED))

    assert result.success is True


@pytest.mark.asyncio
async def test_post_condition_still_fails_a_normal_dispatch_that_wrote_nothing(
    tmp_path: Path,
) -> None:
    _write_tasks(tmp_path)

    result = await DispatchArtifactAction().execute(_post_action(tmp_path, {"response": "hi"}))

    assert result.success is False


@pytest.mark.asyncio
async def test_a_kept_artifact_is_not_stamped(tmp_path: Path) -> None:
    _write_tasks(tmp_path)

    await RevisionStampAction().execute(_post_action(tmp_path, _SKIPPED))

    frontmatter = read_frontmatter(tmp_path / TASKS)
    assert frontmatter is not None and "revision_number" not in frontmatter


@pytest.mark.asyncio
async def test_a_normal_loop_dispatch_is_still_stamped(tmp_path: Path) -> None:
    _write_tasks(tmp_path)

    await RevisionStampAction().execute(_post_action(tmp_path, {"response": "hi"}))

    frontmatter = read_frontmatter(tmp_path / TASKS)
    assert frontmatter is not None and frontmatter.get("revision_number") == 1
