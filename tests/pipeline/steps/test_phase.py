"""Tests for PhaseStepType."""

from __future__ import annotations

import pytest

from squadron.pipeline.models import StepConfig
from squadron.pipeline.steps.phase import PhaseStepType


@pytest.fixture
def design_step() -> PhaseStepType:
    return PhaseStepType("design")


@pytest.fixture
def tasks_step() -> PhaseStepType:
    return PhaseStepType("tasks")


@pytest.fixture
def implement_step() -> PhaseStepType:
    return PhaseStepType("implement")


def _make_config(config: dict[str, object]) -> StepConfig:
    return StepConfig(step_type="design", name="test-step", config=config)


# --- step_type property ---


def test_step_type_design(design_step: PhaseStepType) -> None:
    assert design_step.step_type == "design"


def test_step_type_tasks(tasks_step: PhaseStepType) -> None:
    assert tasks_step.step_type == "tasks"


def test_step_type_implement(implement_step: PhaseStepType) -> None:
    assert implement_step.step_type == "implement"


# --- validate() ---


def test_validate_missing_phase(design_step: PhaseStepType) -> None:
    errors = design_step.validate(_make_config({}))
    assert len(errors) == 1
    assert errors[0].field == "phase"
    assert "required" in errors[0].message


def test_validate_phase_not_int(design_step: PhaseStepType) -> None:
    errors = design_step.validate(_make_config({"phase": "four"}))
    assert len(errors) == 1
    assert errors[0].field == "phase"
    assert "integer" in errors[0].message


def test_validate_valid_full_config(design_step: PhaseStepType) -> None:
    errors = design_step.validate(
        _make_config(
            {
                "phase": 4,
                "model": "opus",
                "review": "slice",
                "checkpoint": "on-concerns",
            }
        )
    )
    assert errors == []


def test_validate_invalid_review_type(design_step: PhaseStepType) -> None:
    errors = design_step.validate(_make_config({"phase": 4, "review": 42}))
    assert len(errors) == 1
    assert errors[0].field == "review"


def test_validate_review_dict_missing_template(design_step: PhaseStepType) -> None:
    errors = design_step.validate(
        _make_config({"phase": 4, "review": {"model": "opus"}})
    )
    assert len(errors) == 1
    assert errors[0].field == "review"
    assert "template" in errors[0].message


def test_validate_invalid_checkpoint(design_step: PhaseStepType) -> None:
    errors = design_step.validate(
        _make_config({"phase": 4, "checkpoint": "invalid-trigger"})
    )
    assert len(errors) == 1
    assert errors[0].field == "checkpoint"
    assert "not a valid" in errors[0].message


def test_validate_invalid_model(design_step: PhaseStepType) -> None:
    errors = design_step.validate(_make_config({"phase": 4, "model": 123}))
    assert len(errors) == 1
    assert errors[0].field == "model"


# --- expand() ---


def test_expand_full_config(design_step: PhaseStepType) -> None:
    """Full config produces 6-action sequence."""
    actions = design_step.expand(
        _make_config(
            {
                "phase": 4,
                "model": "opus",
                "review": "slice",
                "checkpoint": "on-concerns",
            }
        )
    )

    assert len(actions) == 7
    assert actions[0] == ("cf-op", {"operation": "set_phase", "phase": 4})
    assert actions[1] == ("cf-op", {"operation": "set_slice", "slice": "{slice}"})
    assert actions[2] == ("cf-op", {"operation": "build_context"})
    assert actions[3] == ("dispatch", {"model": "opus"})
    assert actions[4] == (
        "review",
        {"template": "slice", "model": None, "slice": "{slice}"},
    )
    assert actions[5] == ("checkpoint", {"trigger": "on-concerns"})
    assert actions[6] == ("commit", {"message_prefix": "phase-4"})


def test_expand_review_as_dict(design_step: PhaseStepType) -> None:
    """Review as dict with template + model override."""
    actions = design_step.expand(
        _make_config(
            {
                "phase": 3,
                "review": {"template": "code", "model": "minimax2.7"},
            }
        )
    )

    review_action = actions[4]
    assert review_action == (
        "review",
        {"template": "code", "model": "minimax2.7", "slice": "{slice}"},
    )


def test_expand_no_review(design_step: PhaseStepType) -> None:
    """No review config omits review and checkpoint (5-action sequence)."""
    actions = design_step.expand(_make_config({"phase": 4}))

    assert len(actions) == 5
    action_types = [a[0] for a in actions]
    assert "review" not in action_types
    assert "checkpoint" not in action_types


def test_expand_review_no_checkpoint(design_step: PhaseStepType) -> None:
    """Review present but no checkpoint defaults trigger to 'never'."""
    actions = design_step.expand(_make_config({"phase": 4, "review": "slice"}))

    assert len(actions) == 7
    checkpoint = actions[5]
    assert checkpoint == ("checkpoint", {"trigger": "never"})


def test_expand_dispatch_model_from_config(design_step: PhaseStepType) -> None:
    actions = design_step.expand(_make_config({"phase": 4, "model": "opus"}))
    dispatch = actions[3]
    assert dispatch == ("dispatch", {"model": "opus"})


def test_expand_dispatch_model_none(design_step: PhaseStepType) -> None:
    actions = design_step.expand(_make_config({"phase": 4}))
    dispatch = actions[3]
    assert dispatch == ("dispatch", {"model": None})


def test_expand_commit_prefix_includes_phase(design_step: PhaseStepType) -> None:
    actions = design_step.expand(_make_config({"phase": 7}))
    commit = actions[-1]
    assert commit == ("commit", {"message_prefix": "phase-7"})


def test_expand_review_includes_slice_placeholder(design_step: PhaseStepType) -> None:
    """Review action tuple includes 'slice' placeholder when review is configured."""
    actions = design_step.expand(_make_config({"phase": 4, "review": "code"}))
    review_action = next(a for a in actions if a[0] == "review")
    assert "slice" in review_action[1]
    assert review_action[1]["slice"] == "{slice}"


def test_expand_no_review_has_no_review_action(design_step: PhaseStepType) -> None:
    """No review sub-field means no review action in the output."""
    actions = design_step.expand(_make_config({"phase": 4}))
    action_types = [a[0] for a in actions]
    assert "review" not in action_types
