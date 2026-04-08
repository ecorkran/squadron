"""Integration tests for slice 158: compact summary persistence and resume."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadron.pipeline.executor import (
    ExecutionStatus,
    StepResult,
    execute_pipeline,
)
from squadron.pipeline.models import (
    ActionResult,
    PipelineDefinition,
    StepConfig,
)
from squadron.pipeline.state import (
    CompactSummary,
    ExecutionMode,
    StateManager,
)
from squadron.pipeline.steps import register_step_type


class _FakeStepType:
    step_type = "fake-dispatch"

    def validate(self, config):  # type: ignore[no-untyped-def]
        return []

    def expand(self, config):  # type: ignore[no-untyped-def]
        return [("dispatch", {})]


register_step_type("fake-dispatch", _FakeStepType())


# ---------------------------------------------------------------------------
# T11 — callback persists compact summary
# ---------------------------------------------------------------------------


def test_step_callback_records_compact_summary(tmp_path: Path) -> None:
    mgr = StateManager(runs_dir=tmp_path)
    run_id = mgr.init_run("test-pipeline", {"slice": "154"})
    cb = mgr.make_step_callback(run_id)

    ar = ActionResult(
        success=True,
        action_type="compact",
        outputs={
            "summary": "the summary text",
            "instructions": "compact this",
            "source_step_index": 3,
            "source_step_name": "compact-mid",
            "summary_model": "haiku-id",
        },
    )
    step_result = StepResult(
        step_name="compact-mid",
        step_type="compact",
        status=ExecutionStatus.COMPLETED,
        action_results=[ar],
    )
    cb(step_result)

    state = mgr.load(run_id)
    assert "3:compact-mid" in state.compact_summaries
    s = state.compact_summaries["3:compact-mid"]
    assert s.text == "the summary text"
    assert s.summary_model == "haiku-id"
    assert s.source_step_index == 3
    assert s.source_step_name == "compact-mid"


def test_step_callback_skips_non_compact(tmp_path: Path) -> None:
    mgr = StateManager(runs_dir=tmp_path)
    run_id = mgr.init_run("test-pipeline", {"slice": "154"})
    cb = mgr.make_step_callback(run_id)

    ar = ActionResult(
        success=True,
        action_type="dispatch",
        outputs={"summary": "x", "source_step_index": 1, "source_step_name": "d"},
    )
    cb(
        StepResult(
            step_name="d",
            step_type="fake-dispatch",
            status=ExecutionStatus.COMPLETED,
            action_results=[ar],
        )
    )
    state = mgr.load(run_id)
    assert state.compact_summaries == {}


# ---------------------------------------------------------------------------
# T12 — executor seeds session from compact summary on resume
# ---------------------------------------------------------------------------


def _make_definition() -> PipelineDefinition:
    return PipelineDefinition(
        name="test-pipeline",
        description="",
        model=None,
        params={"slice": "required"},
        steps=[
            StepConfig(
                step_type="fake-dispatch", name="step0", config={"prompt": "hi"}
            ),
            StepConfig(step_type="fake-dispatch", name="step1", config={}),
            StepConfig(
                step_type="fake-dispatch", name="step2", config={"prompt": "hi2"}
            ),
        ],
    )


def _prepare_paused_state(
    tmp_path: Path, *, with_summary: bool
) -> tuple[StateManager, str]:
    mgr = StateManager(runs_dir=tmp_path)
    run_id = mgr.init_run(
        "test-pipeline", {"slice": "154"}, execution_mode=ExecutionMode.SDK
    )
    state = mgr.load(run_id)
    if with_summary:
        state.compact_summaries["1:step1"] = CompactSummary(
            key="1:step1",
            text="prior summary text",
            summary_model="haiku-id",
            source_step_index=1,
            source_step_name="step1",
            created_at=datetime.now(UTC),
        )
        mgr._write_atomic(  # type: ignore[attr-defined]
            mgr._state_path(run_id),  # type: ignore[attr-defined]
            state.model_dump_json(indent=2),
        )
    return mgr, run_id


def _make_session_mock() -> MagicMock:
    session = MagicMock()
    session.seed_context = AsyncMock()
    session.connect = AsyncMock()
    session.disconnect = AsyncMock()
    session.dispatch = AsyncMock(return_value="ok")
    session.set_model = AsyncMock()
    session.current_model = None
    return session


def _make_noop_action() -> MagicMock:
    action = MagicMock()
    action.execute = AsyncMock(
        return_value=ActionResult(success=True, action_type="dispatch", outputs={})
    )
    return action


@pytest.mark.asyncio
async def test_resume_seeds_from_compact_summary(tmp_path: Path) -> None:
    mgr, run_id = _prepare_paused_state(tmp_path, with_summary=True)

    # Monkeypatch StateManager default constructor path used by executor
    from squadron.pipeline import executor as exec_mod

    orig_cls = exec_mod.__dict__.get("StateManager")  # likely absent
    _ = orig_cls
    # The executor does `from squadron.pipeline.state import StateManager`
    # at call time and calls StateManager() with no args — so we patch the
    # default runs dir via env or patch StateManager itself.
    import squadron.pipeline.state as state_mod

    original = state_mod.StateManager

    class _Patched(original):  # type: ignore[misc,valid-type]
        def __init__(self, runs_dir: Path | None = None) -> None:
            super().__init__(runs_dir=runs_dir or tmp_path)

    state_mod.StateManager = _Patched  # type: ignore[misc]
    try:
        session = _make_session_mock()
        noop = _make_noop_action()
        resolver = MagicMock()
        cf_client = MagicMock()

        await execute_pipeline(
            _make_definition(),
            {"slice": "154"},
            resolver=resolver,
            cf_client=cf_client,
            run_id=run_id,
            start_from="step2",
            sdk_session=session,
            _action_registry={
                "dispatch": noop,
                "compact": noop,
            },
        )
    finally:
        state_mod.StateManager = original  # type: ignore[misc]

    session.seed_context.assert_awaited_once_with("prior summary text")


@pytest.mark.asyncio
async def test_fresh_run_does_not_seed(tmp_path: Path) -> None:
    session = _make_session_mock()
    noop = _make_noop_action()
    await execute_pipeline(
        _make_definition(),
        {"slice": "154"},
        resolver=MagicMock(),
        cf_client=MagicMock(),
        sdk_session=session,
        _action_registry={"dispatch": noop, "compact": noop},
    )
    session.seed_context.assert_not_called()


@pytest.mark.asyncio
async def test_resume_without_summary_does_not_seed(tmp_path: Path) -> None:
    mgr, run_id = _prepare_paused_state(tmp_path, with_summary=False)
    import squadron.pipeline.state as state_mod

    original = state_mod.StateManager

    class _Patched(original):  # type: ignore[misc,valid-type]
        def __init__(self, runs_dir: Path | None = None) -> None:
            super().__init__(runs_dir=runs_dir or tmp_path)

    state_mod.StateManager = _Patched  # type: ignore[misc]
    try:
        session = _make_session_mock()
        noop = _make_noop_action()
        await execute_pipeline(
            _make_definition(),
            {"slice": "154"},
            resolver=MagicMock(),
            cf_client=MagicMock(),
            run_id=run_id,
            start_from="step2",
            sdk_session=session,
            _action_registry={"dispatch": noop, "compact": noop},
        )
    finally:
        state_mod.StateManager = original  # type: ignore[misc]

    session.seed_context.assert_not_called()
