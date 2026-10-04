"""The ``implement`` needs a preceding ``branch: {op: enter}`` rule (slice 196 D4)."""

from __future__ import annotations

from squadron.pipeline.branch_rules import implement_branch_errors
from squadron.pipeline.loader import validate_pipeline
from squadron.pipeline.models import PipelineDefinition, StepConfig


def _enter(name: str = "enter") -> StepConfig:
    return StepConfig(step_type="branch", name=name, config={"op": "enter"})


def _merge() -> StepConfig:
    return StepConfig(step_type="branch", name="merge", config={"op": "merge"})


def _implement(name: str = "implement-0") -> StepConfig:
    return StepConfig(step_type="implement", name=name, config={"phase": 6})


def _container(step_type: str, *body: dict[str, object]) -> StepConfig:
    return StepConfig(step_type=step_type, name=f"{step_type}-0", config={"steps": list(body)})


_RAW_ENTER: dict[str, object] = {"branch": {"op": "enter"}}
_RAW_IMPLEMENT: dict[str, object] = {"implement": {"phase": 6, "name": "inner-implement"}}


def test_flat_enter_then_implement_is_valid() -> None:
    assert implement_branch_errors([_enter(), _implement()]) == []


def test_flat_implement_without_enter_is_an_error_naming_the_fix() -> None:
    errors = implement_branch_errors([_implement("build-it")])

    assert len(errors) == 1
    assert errors[0].message.startswith("implement step build-it needs a preceding branch: {op: enter}")
    assert "- branch: {op: enter}" in errors[0].message


def test_an_enter_after_the_implement_does_not_count() -> None:
    assert len(implement_branch_errors([_implement(), _enter()])) == 1


def test_a_merge_is_not_an_enter() -> None:
    assert len(implement_branch_errors([_merge(), _implement()])) == 1


def test_enter_before_a_containing_each_counts() -> None:
    steps = [_enter(), _container("each", _RAW_IMPLEMENT)]
    assert implement_branch_errors(steps) == []


def test_enter_before_a_containing_loop_counts() -> None:
    steps = [_enter(), _container("loop", _RAW_IMPLEMENT)]
    assert implement_branch_errors(steps) == []


def test_enter_inside_the_container_before_the_implement_counts() -> None:
    steps = [_container("each", _RAW_ENTER, _RAW_IMPLEMENT)]
    assert implement_branch_errors(steps) == []


def test_enter_only_in_a_sibling_container_does_not_count() -> None:
    steps = [_container("each", _RAW_ENTER), _container("each", _RAW_IMPLEMENT)]

    errors = implement_branch_errors(steps)

    assert [e.message.split(" needs")[0] for e in errors] == ["implement step inner-implement"]


def test_enter_inside_a_container_does_not_leak_to_a_later_top_level_implement() -> None:
    steps = [_container("each", _RAW_ENTER), _implement()]
    assert len(implement_branch_errors(steps)) == 1


def test_validate_pipeline_reports_the_rule() -> None:
    definition = PipelineDefinition(
        name="no-enter", description="t", params={}, steps=[_implement("go")]
    )

    messages = [e.message for e in validate_pipeline(definition)]

    assert any("implement step go needs a preceding branch: {op: enter}" in m for m in messages)
