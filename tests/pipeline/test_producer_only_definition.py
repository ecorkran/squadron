"""producer_only_definition and select_producer_step (slice 424, Task 5; design D1)."""

from __future__ import annotations

import copy
import logging

import pytest

from squadron.pipeline.loader import load_pipeline
from squadron.pipeline.models import PipelineDefinition, StepConfig
from squadron.pipeline.producer_only import (
    ProducerOnlyError,
    producer_only_definition,
    select_producer_step,
)


def _top_level_names(pipeline: str) -> list[str]:
    return [step.name for step in load_pipeline(pipeline).steps]


def test_p6_selects_implement_and_skips_every_other_top_level_step_in_order() -> None:
    definition = load_pipeline("P6")
    names = _top_level_names("P6")

    selection = producer_only_definition(definition)

    producer = next(step for step in definition.steps if step.step_type == "implement")
    assert selection.step_name == producer.name
    assert [step.name for step in selection.definition.steps] == [producer.name]
    assert selection.skipped == tuple(name for name in names if name != producer.name)
    assert len(selection.skipped) == len(definition.steps) - 1
    assert "review" not in selection.definition.steps[0].config
    assert "checkpoint" not in selection.definition.steps[0].config


@pytest.mark.parametrize(("pipeline", "step_type"), [("P4", "design"), ("P5", "tasks")])
def test_p4_and_p5_each_have_one_producer(pipeline: str, step_type: str) -> None:
    selection = producer_only_definition(load_pipeline(pipeline))

    assert [step.step_type for step in selection.definition.steps] == [step_type]
    assert selection.step_name == selection.definition.steps[0].name


def test_selection_keeps_definition_level_settings() -> None:
    definition = load_pipeline("P6")
    definition.max_cost_usd = 3.0

    narrowed = producer_only_definition(definition).definition

    assert narrowed.name == definition.name
    assert narrowed.params == definition.params
    assert narrowed.model == definition.model
    assert narrowed.max_cost_usd == 3.0


def test_multi_producer_pipeline_refuses_naming_the_candidates() -> None:
    with pytest.raises(ProducerOnlyError) as raised:
        producer_only_definition(load_pipeline("P456"))

    message = str(raised.value)
    for name in ("design", "tasks", "implement"):
        assert name in message


def test_pipeline_with_no_producer_refuses_listing_its_steps() -> None:
    definition = PipelineDefinition(
        name="no-producer",
        description="",
        params={},
        steps=[
            StepConfig(step_type="branch", name="enter", config={"op": "enter"}),
            StepConfig(step_type="dispatch", name="work", config={"prompt": "x"}),
        ],
    )

    with pytest.raises(ProducerOnlyError) as raised:
        select_producer_step(definition)

    message = str(raised.value)
    assert "no-producer" in message
    assert "enter" in message and "work" in message
    assert "no step type" in message


def test_a_producer_nested_in_a_loop_is_not_a_candidate() -> None:
    inner = StepConfig(step_type="implement", name="inner", config={"phase": 6})
    definition = PipelineDefinition(
        name="nested",
        description="",
        params={},
        steps=[
            StepConfig(
                step_type="loop",
                name="retry",
                config={"max": "2", "steps": [inner]},
            )
        ],
    )

    with pytest.raises(ProducerOnlyError):
        select_producer_step(definition)


def test_input_definition_is_not_mutated() -> None:
    definition = load_pipeline("P6")
    before = copy.deepcopy(definition)

    producer_only_definition(definition)

    assert definition == before
    assert len(definition.steps) == len(before.steps)


def test_refusal_logs_a_warning(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="squadron.pipeline.producer_only"):
        with pytest.raises(ProducerOnlyError):
            producer_only_definition(load_pipeline("P456"))

    assert any(
        record.levelno == logging.WARNING and "p456" in record.getMessage() for record in caplog.records
    )


def test_the_fix_pipeline_selects_its_step_with_nothing_skipped() -> None:
    definition = load_pipeline("fix")

    selection = producer_only_definition(definition)

    assert selection.step_name == definition.steps[0].name
    assert selection.skipped == ()
    assert selection.definition.steps == definition.steps
