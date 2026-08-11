"""Tests for EventType enum, event-typed contexts, and the event registry."""

from __future__ import annotations

import dataclasses

import pytest

import squadron.events as events_pkg
from squadron.events import (
    EventType,
    get_event_action,
    list_event_actions,
    register_event_action,
)
from squadron.events.contexts import CommitContext, EventContext, PostActionContext
from squadron.pipeline.models import ActionResult, ValidationError


class _FakeCfClient:
    """Minimal duck-typed CfClientProtocol stand-in for context tests."""

    def list_slices(self) -> list[object]:
        return []

    def list_tasks(self) -> list[object]:
        return []

    def get_project(self) -> object:
        return object()


class _FakeAction:
    """Minimal class satisfying the EventAction protocol for testing."""

    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def events(self) -> frozenset[EventType]:
        return frozenset({EventType.COMMIT})

    def validate(self, config: dict[str, object]) -> list[ValidationError]:
        return []

    async def execute(self, context: EventContext) -> ActionResult:
        return ActionResult(success=True, action_type=self._name, outputs={})


@pytest.fixture(autouse=True)
def _clear_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate each test by resetting the event action registry."""
    monkeypatch.setattr(events_pkg, "_REGISTRY", {})


def test_event_type_values() -> None:
    assert EventType.COMMIT == "commit"
    assert EventType.POST_ACTION == "post-action"
    assert {member.value for member in EventType} == {"commit", "post-action"}


def test_register_and_get_well_formed_action() -> None:
    action = _FakeAction("demo.rule-check")
    register_event_action(action)
    retrieved = get_event_action("demo.rule-check")
    assert retrieved is action
    assert "demo.rule-check" in list_event_actions()


def test_register_undotted_name_raises() -> None:
    with pytest.raises(ValueError, match="namespaced"):
        register_event_action(_FakeAction("nodothere"))


def test_register_duplicate_name_raises() -> None:
    register_event_action(_FakeAction("demo.rule-check"))
    with pytest.raises(ValueError, match="already registered"):
        register_event_action(_FakeAction("demo.rule-check"))


def test_register_squadron_prefix_from_outside_builtin_raises() -> None:
    with pytest.raises(ValueError, match="reserved 'squadron.' prefix"):
        register_event_action(_FakeAction("squadron.not-a-builtin"))


def test_get_unknown_action_raises_naming_available() -> None:
    register_event_action(_FakeAction("demo.rule-check"))
    with pytest.raises(KeyError, match="demo.rule-check"):
        get_event_action("nonexistent")


def test_list_event_actions_empty() -> None:
    assert list_event_actions() == []


class TestContextsFrozen:
    def test_event_context_is_frozen(self) -> None:
        ctx = EventContext(event=EventType.COMMIT, cwd=".", params={})
        with pytest.raises(dataclasses.FrozenInstanceError):
            ctx.cwd = "/other"  # type: ignore[misc]

    def test_commit_context_is_frozen(self) -> None:
        ctx = CommitContext(event=EventType.COMMIT, cwd=".", params={}, staged_paths=())
        with pytest.raises(dataclasses.FrozenInstanceError):
            ctx.staged_paths = ("a.md",)  # type: ignore[misc]

    def test_post_action_context_carries_full_field_list(self) -> None:
        result = ActionResult(success=True, action_type="dispatch", outputs={})
        ctx = PostActionContext(
            event=EventType.POST_ACTION,
            cwd=".",
            params={},
            action_type="dispatch",
            result=result,
            run_id="run-1",
            run_started_at=None,
            run_state_error=None,
            step_name="design-0",
            step_type="design",
            expected_artifact_kind=None,
            iteration=0,
            cf_client=_FakeCfClient(),
        )
        assert ctx.action_type == "dispatch"
        assert ctx.result is result
        assert ctx.run_id == "run-1"
        assert ctx.run_started_at is None
        assert ctx.run_state_error is None
        assert ctx.step_name == "design-0"
        assert ctx.step_type == "design"
        assert ctx.expected_artifact_kind is None
        assert ctx.iteration == 0
        with pytest.raises(dataclasses.FrozenInstanceError):
            ctx.iteration = 1  # type: ignore[misc]
