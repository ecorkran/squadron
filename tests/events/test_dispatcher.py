"""Tests for the event dispatcher (design D4/D5)."""

from __future__ import annotations

import asyncio

import pytest

import squadron.events as events_pkg
from squadron.events import EventType, register_event_action
from squadron.events.contexts import CommitContext, EventContext
from squadron.events.dispatcher import OutcomeErrorKind, fire
from squadron.events.manifest import Binding
from squadron.pipeline.models import ActionResult, ValidationError


class _FakeAction:
    """Records calls; returns a configurable result / raises / hangs."""

    def __init__(
        self,
        name: str,
        *,
        success: bool = True,
        raises: bool = False,
        hangs: bool = False,
    ) -> None:
        self._name = name
        self._success = success
        self._raises = raises
        self._hangs = hangs
        self.call_count = 0

    @property
    def name(self) -> str:
        return self._name

    @property
    def events(self) -> frozenset[EventType]:
        return frozenset({EventType.COMMIT, EventType.POST_ACTION})

    def validate(self, config: dict[str, object]) -> list[ValidationError]:
        return []

    async def execute(self, context: EventContext) -> ActionResult:
        self.call_count += 1
        if self._raises:
            raise RuntimeError(f"{self._name} is broken")
        if self._hangs:
            await asyncio.sleep(10)
        return ActionResult(success=self._success, action_type=self._name, outputs={})


@pytest.fixture(autouse=True)
def _clear_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(events_pkg, "_REGISTRY", {})


def _set_timeout(monkeypatch: pytest.MonkeyPatch, seconds: int) -> None:
    from squadron.config import keys as keys_module

    monkeypatch.setitem(
        keys_module.CONFIG_KEYS,
        "events.timeout_seconds",
        keys_module.ConfigKey(
            name="events.timeout_seconds", type_=int, default=seconds, description="test override"
        ),
    )


def _commit_context() -> CommitContext:
    return CommitContext(event=EventType.COMMIT, cwd=".", params={}, staged_paths=("a.md",))


def _post_action_context() -> EventContext:
    return EventContext(event=EventType.POST_ACTION, cwd=".", params={})


@pytest.mark.asyncio
async def test_commit_runs_all_bindings_even_after_a_failure() -> None:
    first = _FakeAction("demo.first", success=False)
    second = _FakeAction("demo.second", success=True)
    register_event_action(first)
    register_event_action(second)
    bindings = [
        Binding(event=EventType.COMMIT, action="demo.first", params={}, source="built-in"),
        Binding(event=EventType.COMMIT, action="demo.second", params={}, source="built-in"),
    ]

    outcomes = await fire(_commit_context(), bindings)

    assert first.call_count == 1
    assert second.call_count == 1
    assert len(outcomes) == 2
    assert outcomes[0].result is not None and outcomes[0].result.success is False
    assert outcomes[1].result is not None and outcomes[1].result.success is True


@pytest.mark.asyncio
async def test_post_action_stops_at_first_failure() -> None:
    first = _FakeAction("demo.first", success=False)
    second = _FakeAction("demo.second", success=True)
    register_event_action(first)
    register_event_action(second)
    bindings = [
        Binding(event=EventType.POST_ACTION, action="demo.first", params={}, source="built-in"),
        Binding(event=EventType.POST_ACTION, action="demo.second", params={}, source="built-in"),
    ]

    outcomes = await fire(_post_action_context(), bindings)

    assert first.call_count == 1
    assert second.call_count == 0
    assert len(outcomes) == 1


@pytest.mark.asyncio
async def test_timeout_treated_as_fail_naming_action(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _set_timeout(monkeypatch, 0)
    hanging = _FakeAction("demo.hangs", hangs=True)
    register_event_action(hanging)
    bindings = [Binding(event=EventType.COMMIT, action="demo.hangs", params={}, source="built-in")]

    with caplog.at_level("WARNING"):
        outcomes = await fire(_commit_context(), bindings)

    assert outcomes[0].error_kind is OutcomeErrorKind.TIMEOUT
    assert outcomes[0].result is None
    assert any("demo.hangs" in rec.message for rec in caplog.records)


@pytest.mark.asyncio
async def test_raise_treated_as_fail_with_error_log(caplog: pytest.LogCaptureFixture) -> None:
    broken = _FakeAction("demo.broken", raises=True)
    register_event_action(broken)
    bindings = [Binding(event=EventType.COMMIT, action="demo.broken", params={}, source="built-in")]

    with caplog.at_level("ERROR"):
        outcomes = await fire(_commit_context(), bindings)

    assert outcomes[0].error_kind is OutcomeErrorKind.RAISED
    assert outcomes[0].result is None
    assert any("demo.broken" in rec.message for rec in caplog.records)


@pytest.mark.asyncio
async def test_success_logs_duration_at_debug(caplog: pytest.LogCaptureFixture) -> None:
    ok = _FakeAction("demo.ok", success=True)
    register_event_action(ok)
    bindings = [Binding(event=EventType.COMMIT, action="demo.ok", params={}, source="built-in")]

    with caplog.at_level("DEBUG"):
        outcomes = await fire(_commit_context(), bindings)

    assert outcomes[0].error_kind is OutcomeErrorKind.NONE
    assert outcomes[0].result is not None and outcomes[0].result.success is True
    assert any("demo.ok" in rec.message and rec.levelname == "DEBUG" for rec in caplog.records)


@pytest.mark.asyncio
async def test_post_action_stops_on_raise_too() -> None:
    broken = _FakeAction("demo.broken", raises=True)
    second = _FakeAction("demo.second", success=True)
    register_event_action(broken)
    register_event_action(second)
    bindings = [
        Binding(event=EventType.POST_ACTION, action="demo.broken", params={}, source="built-in"),
        Binding(event=EventType.POST_ACTION, action="demo.second", params={}, source="built-in"),
    ]

    outcomes = await fire(_post_action_context(), bindings)

    assert second.call_count == 0
    assert len(outcomes) == 1
    assert outcomes[0].error_kind is OutcomeErrorKind.RAISED
