"""PhaseStepType.producer_only_config (slice 424, Task 4; design D1, D2)."""

from __future__ import annotations

import copy

import pytest

from squadron.pipeline.commit_plan import REVIEW_TEMPLATE_PARAM
from squadron.pipeline.loader import load_pipeline
from squadron.pipeline.models import StepConfig
from squadron.pipeline.producer_only import ProducerStep
from squadron.pipeline.steps import bootstrap_step_types, get_step_type
from squadron.pipeline.steps.phase import PhaseStepType

#: Action types that only exist because the step embeds a review.
_REVIEW_ACTIONS = frozenset({"review", "checkpoint"})


def _step(pipeline: str, step_type: str) -> StepConfig:
    definition = load_pipeline(pipeline)
    return next(step for step in definition.steps if step.step_type == step_type)


def _expand(config: StepConfig) -> list[tuple[str, dict[str, object]]]:
    bootstrap_step_types()
    return get_step_type(config.step_type).expand(config)


def _producer(config: StepConfig) -> StepConfig:
    bootstrap_step_types()
    step_type = get_step_type(config.step_type)
    assert isinstance(step_type, ProducerStep)
    return step_type.producer_only_config(config)


def test_phase_step_type_is_a_producer_step() -> None:
    assert isinstance(PhaseStepType("implement"), ProducerStep)


def test_stripped_implement_expands_to_the_full_actions_minus_review_and_checkpoint() -> None:
    full = _step("P6", "implement")
    stripped = _producer(full)

    full_actions = _expand(full)
    stripped_actions = _expand(stripped)

    assert [action for action, _ in full_actions if action in _REVIEW_ACTIONS] == [
        "review",
        "checkpoint",
    ]
    expected = [(action, cfg) for action, cfg in full_actions if action not in _REVIEW_ACTIONS]
    # Everything but the commit's review template is byte-identical.
    for (expected_action, expected_cfg), (action, cfg) in zip(expected, stripped_actions, strict=True):
        assert action == expected_action
        if action == "commit":
            assert REVIEW_TEMPLATE_PARAM in expected_cfg
            without_template = {k: v for k, v in expected_cfg.items() if k != REVIEW_TEMPLATE_PARAM}
            assert cfg == without_template
        else:
            assert cfg == expected_cfg


def test_cf_ops_and_existing_keep_are_unchanged() -> None:
    full = _step("P6", "implement")
    stripped = _producer(full)

    def lead(config: StepConfig) -> list[tuple[str, dict[str, object]]]:
        return [pair for pair in _expand(config) if pair[0] not in {*_REVIEW_ACTIONS, "commit"}]

    assert lead(stripped) == lead(full)
    assert stripped.config["existing"] == full.config["existing"] == "keep"
    assert [(action, cfg.get("operation")) for action, cfg in lead(stripped)] == [
        ("cf-op", "set_slice"),
        ("cf-op", "check_decisions"),
        ("cf-op", "set_phase"),
        ("cf-op", "build_context"),
        ("dispatch", None),
    ]


@pytest.mark.parametrize(("pipeline", "step_type"), [("P4", "design"), ("P5", "tasks")])
def test_design_and_tasks_steps_are_producer_steps(pipeline: str, step_type: str) -> None:
    config = _step(pipeline, step_type)
    stripped = _producer(config)

    assert "review" not in stripped.config
    assert "checkpoint" not in stripped.config
    assert not {action for action, _ in _expand(stripped)} & _REVIEW_ACTIONS


def test_input_config_is_not_mutated() -> None:
    full = _step("P6", "implement")
    before = copy.deepcopy(full)

    stripped = _producer(full)

    assert full == before
    assert stripped is not full
    assert stripped.config is not full.config
    assert (stripped.step_type, stripped.name) == (full.step_type, full.name)


def test_a_step_with_no_review_returns_an_equal_config() -> None:
    config = StepConfig(
        step_type="implement",
        name="implement",
        config={"phase": 6, "model": "m", "existing": "keep"},
    )

    stripped = PhaseStepType("implement").producer_only_config(config)

    assert stripped == config
    assert stripped is not config
