"""Tests for Action protocol, ActionType enum, and action registry."""

from __future__ import annotations

import pytest

import squadron.pipeline.actions as actions_pkg
from squadron.pipeline.actions import (
    Action,
    ActionType,
    get_action,
    list_actions,
    register_action,
)
from squadron.pipeline.models import ActionContext, ActionResult, ValidationError


class _MinimalAction:
    """Minimal class satisfying the Action protocol for testing."""

    @property
    def action_type(self) -> str:
        return "dispatch"

    async def execute(self, context: ActionContext) -> ActionResult:
        return ActionResult(success=True, action_type=self.action_type, outputs={})

    def validate(self, config: dict[str, object]) -> list[ValidationError]:
        return []


@pytest.fixture(autouse=True)
def _clear_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate each test by resetting the action registry."""
    monkeypatch.setattr(actions_pkg, "_REGISTRY", {})


def test_action_type_values() -> None:
    assert ActionType.DISPATCH == "dispatch"
    assert ActionType.CF_OP == "cf-op"
    assert ActionType.COMPACT == "compact"


def test_register_and_get_action() -> None:
    obj = _MinimalAction()
    register_action("dispatch", obj)
    retrieved = get_action("dispatch")
    assert retrieved is obj
    assert isinstance(obj, Action)


def test_get_unregistered_action_raises() -> None:
    with pytest.raises(KeyError):
        get_action("nonexistent")


def test_list_actions() -> None:
    register_action("dispatch", _MinimalAction())
    register_action("review", _MinimalAction())
    result = list_actions()
    assert "dispatch" in result
    assert "review" in result


def test_list_actions_empty() -> None:
    assert list_actions() == []
