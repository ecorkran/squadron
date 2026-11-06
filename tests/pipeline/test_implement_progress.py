"""An implement dispatch is held to its task file (issue #293)."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadron.core.usage import RunTelemetry
from squadron.integrations.context_forge import ProjectInfo, SliceEntry, TaskEntry
from squadron.pipeline.actions.dispatch import DispatchAction
from squadron.pipeline.failure_kind import FAILURE_KIND_KEY, FailureKind
from squadron.pipeline.implement_progress import (
    MAX_STALLED_CONTINUATIONS,
    TaskProgress,
    continuation_prompt,
    continue_until_finished,
    implement_slice_index,
    read_task_progress,
)
from squadron.pipeline.models import ActionContext
from squadron.pipeline.resolver import ResolvedModel
from squadron.pipeline.sdk_session import SDKExecutionSession
from squadron.pipeline.sdk_turns import SessionReply
from squadron.pipeline.steps import StepTypeName
from squadron.pipeline.steps.phase import RULES_STEP_PARAM
from squadron.pipeline.usage_capture import UsageCapture
from squadron.providers.errors import ProviderError
from tests.pipeline.conftest import session_reply

SLICE = 105
TASKS = "project-documents/user/tasks/105-tasks.stub.md"
_LOGGER = "squadron.pipeline.implement_progress"


def _cf() -> MagicMock:
    client = MagicMock()
    client.list_slices.return_value = [
        SliceEntry(
            index=SLICE,
            name="Stub",
            design_file="project-documents/user/slices/105-slice.stub.md",
            status="in_progress",
            retroactive=False,
        )
    ]
    client.list_tasks.return_value = [TaskEntry(index=SLICE, files=["105-tasks.stub.md"])]
    client.get_project.return_value = ProjectInfo(
        arch_file="a.md", slice_plan="p", phase="Phase 6", slice=str(SLICE), name="squadron"
    )
    return client


def _write(cwd: Path, *lines: str) -> None:
    path = cwd / TASKS
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\ndocType: tasks\n---\n# tasks\n\n" + "\n".join(lines) + "\n")


def _check_off_first_item(cwd: Path) -> None:
    path = cwd / TASKS
    path.write_text(path.read_text().replace("- [ ]", "- [x]", 1))


def _session(on_dispatch: Callable[[], None]) -> AsyncMock:
    """A session whose every dispatch runs ``on_dispatch`` and costs one turn."""
    session = AsyncMock(spec=SDKExecutionSession)

    async def dispatch(prompt: str) -> SessionReply:
        on_dispatch()
        return SessionReply(text=f"reply to {prompt[:10]}", telemetry=RunTelemetry(turns=1))

    session.dispatch = AsyncMock(side_effect=dispatch)
    return session


def _first_reply() -> SessionReply:
    return SessionReply(text="first", telemetry=RunTelemetry(turns=3))


# ---------------------------------------------------------------------------
# read_task_progress
# ---------------------------------------------------------------------------


def test_progress_lists_unchecked_items_and_blocked_markers(tmp_path: Path) -> None:
    _write(tmp_path, "- [x] 1.1 done", "- [ ] 1.2 open", "> BLOCKED: needs the PM")

    progress = read_task_progress(_cf(), SLICE, str(tmp_path))

    assert progress.unchecked == ("1.2 open",)
    assert progress.blocked == ("needs the PM",)
    assert progress.needs_continuation is False


def test_progress_of_a_finished_file_needs_nothing(tmp_path: Path) -> None:
    _write(tmp_path, "- [x] 1.1 done")

    progress = read_task_progress(_cf(), SLICE, str(tmp_path))

    assert progress == TaskProgress(unchecked=(), blocked=())
    assert progress.needs_continuation is False


def test_progress_fails_on_an_unreadable_task_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_task_progress(_cf(), SLICE, str(tmp_path))


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({RULES_STEP_PARAM: StepTypeName.IMPLEMENT, "slice": "105"}, SLICE),
        ({RULES_STEP_PARAM: StepTypeName.IMPLEMENT}, None),
        ({RULES_STEP_PARAM: StepTypeName.DESIGN, "slice": "105"}, None),
        ({"slice": "105"}, None),
    ],
)
def test_only_a_slice_implement_dispatch_is_held_to_its_tasks(
    params: dict[str, object], expected: int | None
) -> None:
    assert implement_slice_index(params) == expected


# ---------------------------------------------------------------------------
# continue_until_finished
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_session_that_finishes_after_one_continuation_returns_combined_reply(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _write(tmp_path, "- [ ] 1.1 open")
    session = _session(lambda: _check_off_first_item(tmp_path))

    def read() -> TaskProgress:
        return read_task_progress(_cf(), SLICE, str(tmp_path))

    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        reply, progress = await continue_until_finished(session, _first_reply(), read)

    session.dispatch.assert_awaited_once()
    assert "1 unchecked item(s)" in session.dispatch.await_args.args[0]
    assert progress.unchecked == ()
    assert reply.text.startswith("first\n\nreply to ")
    assert reply.telemetry.turns == 4
    assert any("1 unchecked task item(s)" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_progress_each_round_keeps_the_session_going_past_the_stall_bound(
    tmp_path: Path,
) -> None:
    items = [f"- [ ] 1.{n} open" for n in range(MAX_STALLED_CONTINUATIONS + 2)]
    _write(tmp_path, *items)
    session = _session(lambda: _check_off_first_item(tmp_path))

    _, progress = await continue_until_finished(
        session, _first_reply(), lambda: read_task_progress(_cf(), SLICE, str(tmp_path))
    )

    assert progress.unchecked == ()
    assert session.dispatch.await_count == len(items)


@pytest.mark.asyncio
async def test_a_session_that_checks_nothing_off_stops_after_the_stall_bound(
    tmp_path: Path,
) -> None:
    _write(tmp_path, "- [ ] 1.1 open")
    session = _session(lambda: None)

    reply, progress = await continue_until_finished(
        session, _first_reply(), lambda: read_task_progress(_cf(), SLICE, str(tmp_path))
    )

    assert session.dispatch.await_count == MAX_STALLED_CONTINUATIONS
    assert progress.unchecked == ("1.1 open",)
    assert progress.needs_continuation is True
    assert reply.telemetry.turns == 3 + MAX_STALLED_CONTINUATIONS


@pytest.mark.asyncio
async def test_a_blocked_marker_ends_the_loop_without_a_continuation(tmp_path: Path) -> None:
    _write(tmp_path, "- [ ] 1.1 open", "BLOCKED: waiting on the PM")
    session = _session(lambda: None)

    _, progress = await continue_until_finished(
        session, _first_reply(), lambda: read_task_progress(_cf(), SLICE, str(tmp_path))
    )

    session.dispatch.assert_not_awaited()
    assert progress.blocked == ("waiting on the PM",)


@pytest.mark.asyncio
async def test_a_provider_error_in_a_continuation_carries_every_rounds_spend(
    tmp_path: Path,
) -> None:
    _write(tmp_path, "- [ ] 1.1 open")
    session = AsyncMock(spec=SDKExecutionSession)
    failure = ProviderError("boom")
    failure.telemetry = RunTelemetry(turns=2)
    session.dispatch = AsyncMock(side_effect=failure)

    with pytest.raises(ProviderError) as raised:
        await continue_until_finished(
            session, _first_reply(), lambda: read_task_progress(_cf(), SLICE, str(tmp_path))
        )

    assert raised.value.telemetry is not None
    assert raised.value.telemetry.turns == 5


def test_the_continuation_prompt_forbids_waiting_on_a_background_agent() -> None:
    prompt = continuation_prompt(TaskProgress(unchecked=("1.1 open",), blocked=()))

    assert "1.1 open" in prompt
    assert "never in the background" in prompt
    assert "BLOCKED:" in prompt


# ---------------------------------------------------------------------------
# DispatchAction on the SDK session path
# ---------------------------------------------------------------------------


def _implement_context(session: AsyncMock, cwd: Path) -> ActionContext:
    resolver = MagicMock()
    resolver.resolve.return_value = ("claude-sonnet-4-5", None)
    resolver.resolve_full.return_value = ResolvedModel("claude-sonnet-4-5", None)
    session.set_model = AsyncMock()
    session.effort = None
    session.background_tasks_waited = 0
    session.background_tasks_stopped = 0
    session.background_shells_running = 0
    return ActionContext(
        pipeline_name="p",
        run_id="run-1",
        params={
            "prompt": "implement it",
            "slice": str(SLICE),
            RULES_STEP_PARAM: StepTypeName.IMPLEMENT,
        },
        step_name="implement-1",
        step_index=1,
        prior_outputs={},
        resolver=resolver,
        cf_client=_cf(),
        cwd=str(cwd),
        usage_capture=UsageCapture(set()),
        sdk_session=session,
    )


@pytest.mark.asyncio
async def test_implement_dispatch_continues_until_the_task_file_is_done(tmp_path: Path) -> None:
    _write(tmp_path, "- [ ] 1.1 open")
    session = _session(lambda: _check_off_first_item(tmp_path))
    session.dispatch.side_effect = _first_call_is_inert(session.dispatch.side_effect)

    result = await DispatchAction().execute(_implement_context(session, tmp_path))

    assert result.success is True
    assert session.dispatch.await_count == 2
    assert str(result.outputs["response"]).startswith("reply to implement it\n\nreply to ")


@pytest.mark.asyncio
async def test_implement_dispatch_fails_when_items_stay_unchecked(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _write(tmp_path, "- [ ] 1.1 open")
    session = _session(lambda: None)

    with caplog.at_level(logging.WARNING):
        result = await DispatchAction().execute(_implement_context(session, tmp_path))

    assert result.success is False
    assert result.metadata[FAILURE_KIND_KEY] == FailureKind.UNFINISHED_TASKS.value
    assert "1 unchecked task item(s)" in (result.error or "")
    assert "1.1 open" in (result.error or "")
    assert any(
        r.levelno >= logging.WARNING and "unchecked task item(s)" in r.getMessage()
        for r in caplog.records
    )


@pytest.mark.asyncio
async def test_implement_dispatch_with_a_blocked_marker_is_left_to_the_hand_off(
    tmp_path: Path,
) -> None:
    _write(tmp_path, "- [ ] 1.1 open", "BLOCKED: waiting on the PM")
    session = _session(lambda: None)

    result = await DispatchAction().execute(_implement_context(session, tmp_path))

    assert result.success is True
    session.dispatch.assert_awaited_once()


def _first_call_is_inert(
    later: Callable[[str], Awaitable[SessionReply]],
) -> Callable[[str], Awaitable[SessionReply]]:
    """A dispatch whose first call replies and touches nothing; later calls run ``later``."""
    calls = 0

    async def dispatch(prompt: str) -> SessionReply:
        nonlocal calls
        calls += 1
        if calls == 1:
            return session_reply("reply to implement it")
        return await later(prompt)

    return dispatch
