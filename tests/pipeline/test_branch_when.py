"""Branch ``when``: a param turns a branch op off (#245, Amoeba S11)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from squadron.pipeline.actions.branch import BranchAction, parse_when
from squadron.pipeline.branch_ops import MERGED_OUTPUT, SKIPPED_OUTPUT
from squadron.pipeline.loader import load_pipeline
from squadron.pipeline.models import ActionContext, StepConfig
from squadron.pipeline.prompt_renderer import (
    _render_branch,  # pyright: ignore[reportPrivateUsage]
)
from squadron.pipeline.steps.branch import BranchStepType

_CODE_PIPELINES = ("P6", "implement", "P456", "P56", "implement-plan")


def _step(config: dict[str, object]) -> StepConfig:
    return StepConfig(step_type="branch", name="branch-0", config=config)


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, True), (True, True), (False, False), ("true", True), (" FALSE ", False)],
)
def test_parse_when(value: object, expected: bool) -> None:
    assert parse_when(value) is expected


@pytest.mark.parametrize("value", ["{merge}", "no", "", "0"])
def test_parse_when_rejects_anything_else(value: str) -> None:
    with pytest.raises(ValueError, match="must be true or false"):
        parse_when(value)


def test_step_accepts_when_and_passes_it_to_the_action() -> None:
    step = _step({"op": "merge", "when": "{merge}"})

    assert BranchStepType().validate(step) == []
    [(_, params)] = BranchStepType().expand(step)
    assert params["when"] == "{merge}"


def test_step_rejects_a_non_string_when() -> None:
    errors = BranchStepType().validate(_step({"op": "merge", "when": 3}))
    assert [e.field for e in errors] == ["when"]


def test_step_without_when_passes_no_when() -> None:
    [(_, params)] = BranchStepType().expand(_step({"op": "merge"}))
    assert "when" not in params


def _context(params: dict[str, object]) -> ActionContext:
    return ActionContext(
        pipeline_name="p",
        run_id="r",
        params=params,
        step_name="branch-0",
        step_index=0,
        prior_outputs={},
        resolver=MagicMock(),
        cf_client=MagicMock(),
        cwd="/nonexistent",
    )


@pytest.mark.asyncio
async def test_action_with_when_false_skips_without_touching_git() -> None:
    result = await BranchAction().execute(_context({"op": "merge", "slice": "105", "when": "false"}))

    assert result.success
    assert result.outputs == {SKIPPED_OUTPUT: True}
    assert MERGED_OUTPUT not in result.outputs


@pytest.mark.asyncio
async def test_action_with_an_unresolved_when_fails_the_step() -> None:
    result = await BranchAction().execute(_context({"op": "merge", "slice": "105", "when": "{merge}"}))

    assert not result.success
    assert "must be true or false" in (result.error or "")


def test_prompt_only_render_passes_when_to_sq_branch() -> None:
    rendered = _render_branch({"op": "merge", "slice": "105", "when": "False"}, {})
    assert rendered.command == "sq _branch merge --slice 105 --when false"


def _all_steps(steps: list[StepConfig]) -> list[StepConfig]:
    """Every branch step, including those inside an ``each`` body."""
    found: list[StepConfig] = []
    for step in steps:
        if step.step_type == "branch":
            found.append(step)
        nested = step.config.get("steps")
        if isinstance(nested, list):
            found += _all_steps([_as_step(raw) for raw in nested])  # type: ignore[arg-type]
    return found


def _as_step(raw: dict[str, object]) -> StepConfig:
    ((step_type, config),) = raw.items()
    return StepConfig(
        step_type=step_type, name=step_type, config=config if isinstance(config, dict) else {}
    )  # type: ignore[arg-type]


@pytest.mark.parametrize("name", _CODE_PIPELINES)
def test_code_pipelines_merge_by_default_behind_the_merge_param(name: str) -> None:
    definition = load_pipeline(name)
    merge = next(s for s in _all_steps(definition.steps) if s.config.get("op") == "merge")

    assert definition.params["merge"] == "true"
    assert merge.config["when"] == "{merge}"
