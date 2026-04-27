"""Integration tests — verify all registered step types coexist."""

from __future__ import annotations

import squadron.pipeline.steps.compact  # noqa: F401
import squadron.pipeline.steps.devlog  # noqa: F401
import squadron.pipeline.steps.phase  # noqa: F401
import squadron.pipeline.steps.review  # noqa: F401
from squadron.pipeline.steps import (
    StepType,
    StepTypeName,
    bootstrap_step_types,
    get_step_type,
    list_step_types,
)
from squadron.pipeline.steps.compact import CompactStepType
from squadron.pipeline.steps.devlog import DevlogStepType
from squadron.pipeline.steps.phase import PhaseStepType
from squadron.pipeline.steps.review import ReviewStepType


def test_list_step_types_includes_all_registered() -> None:
    step_types = list_step_types()
    assert "design" in step_types
    assert "tasks" in step_types
    assert "implement" in step_types
    assert "compact" in step_types
    assert "review" in step_types
    assert "devlog" in step_types


def test_get_step_type_design() -> None:
    step = get_step_type("design")
    assert isinstance(step, PhaseStepType)
    assert isinstance(step, StepType)


def test_get_step_type_tasks() -> None:
    step = get_step_type("tasks")
    assert isinstance(step, PhaseStepType)
    assert isinstance(step, StepType)


def test_get_step_type_implement() -> None:
    step = get_step_type("implement")
    assert isinstance(step, PhaseStepType)
    assert isinstance(step, StepType)


def test_get_step_type_compact() -> None:
    step = get_step_type("compact")
    assert isinstance(step, CompactStepType)
    assert isinstance(step, StepType)


def test_get_step_type_review() -> None:
    step = get_step_type("review")
    assert isinstance(step, ReviewStepType)
    assert isinstance(step, StepType)


def test_get_step_type_devlog() -> None:
    step = get_step_type("devlog")
    assert isinstance(step, DevlogStepType)
    assert isinstance(step, StepType)


def test_no_import_errors() -> None:
    """Importing all step type modules should not raise."""
    assert True


def test_bootstrap_step_types_registers_every_canonical_name() -> None:
    """After bootstrap_step_types(), every StepTypeName must resolve.

    Guards against drift between StepTypeName and the bootstrap import
    list. If a new step type is added to StepTypeName but not to
    bootstrap_step_types(), this test fails.
    """
    bootstrap_step_types()
    registered = set(list_step_types())
    expected = {name.value for name in StepTypeName}
    missing = expected - registered
    assert not missing, f"StepTypeName entries not registered: {missing}"


def test_bootstrap_resolves_loop_collection_fan_out() -> None:
    """Regression: prompt-only path used to miss these three step types."""
    bootstrap_step_types()
    for name in ("loop", "each", "fan_out"):
        get_step_type(name)  # raises KeyError on miss
