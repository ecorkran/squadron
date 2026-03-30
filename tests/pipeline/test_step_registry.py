"""Tests for StepType protocol, StepTypeName enum, and step-type registry."""

from __future__ import annotations

import pytest

import squadron.pipeline.steps as steps_pkg
from squadron.pipeline.steps import (
    StepType,
    StepTypeName,
    get_step_type,
    list_step_types,
    register_step_type,
)
from squadron.pipeline.models import StepConfig, ValidationError


class _MinimalStepType:
    """Minimal class satisfying the StepType protocol for testing."""

    @property
    def step_type(self) -> str:
        return "design"

    def expand(self, config: StepConfig) -> list[tuple[str, dict[str, object]]]:
        return []

    def validate(self, config: StepConfig) -> list[ValidationError]:
        return []


@pytest.fixture(autouse=True)
def _clear_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate each test by resetting the step-type registry."""
    monkeypatch.setattr(steps_pkg, "_REGISTRY", {})


def test_step_type_name_values() -> None:
    assert StepTypeName.DESIGN == "design"
    assert StepTypeName.EACH == "each"


def test_register_and_get_step_type() -> None:
    obj = _MinimalStepType()
    register_step_type("design", obj)
    retrieved = get_step_type("design")
    assert retrieved is obj
    assert isinstance(obj, StepType)


def test_get_unregistered_step_type_raises() -> None:
    with pytest.raises(KeyError):
        get_step_type("nonexistent")


def test_list_step_types() -> None:
    register_step_type("design", _MinimalStepType())
    register_step_type("tasks", _MinimalStepType())
    result = list_step_types()
    assert "design" in result
    assert "tasks" in result


def test_list_step_types_empty() -> None:
    assert list_step_types() == []
