"""Per-reviewer call options (slice 437, D2, D3), for both entry points' options shapes."""

from __future__ import annotations

from typing import Any

import pytest

from squadron.project_rules.render import RULES_SEPARATOR
from squadron.recipes.recipe import ReviewerOptions
from squadron.recipes.reviewer_options import reviewer_call_options

STEP_RULES = "step rules"
REVIEWER_RULES = "line pass rules"
#: The options dicts the two entry points build (cli/commands/review_recipe.py and
#: pipeline/actions/review_recipe.py); the CLI carries ``no_tools``, the action does not.
CLI_SHAPE: dict[str, Any] = {"rules_content": STEP_RULES, "verbosity": 1, "no_tools": False}
ACTION_SHAPE: dict[str, Any] = {
    "rules_content": STEP_RULES,
    "allowed_tools": ["Read"],
    "pricing_warned": set(),
}
SHAPES = pytest.mark.parametrize("shape", [CLI_SHAPE, ACTION_SHAPE], ids=["cli", "action"])


def _with_rules(options: ReviewerOptions, content: str) -> ReviewerOptions:
    return options.model_copy(update={"rules": "r.md", "rules_content": content})


@SHAPES
def test_no_options_returns_an_equal_copy_and_does_not_mutate(shape: dict[str, Any]) -> None:
    before = dict(shape)
    result = reviewer_call_options(shape, None)
    assert result == shape and result is not shape
    result["extra"] = 1
    assert shape == before


@SHAPES
def test_tools_false_sets_no_tools(shape: dict[str, Any]) -> None:
    assert reviewer_call_options(shape, ReviewerOptions(tools=False))["no_tools"] is True


@SHAPES
def test_tools_true_leaves_the_steps_no_tools_as_it_was(shape: dict[str, Any]) -> None:
    result = reviewer_call_options({**shape, "no_tools": True}, ReviewerOptions(tools=True))
    assert result["no_tools"] is True
    assert reviewer_call_options(shape, ReviewerOptions(tools=True)).get("no_tools") == shape.get(
        "no_tools"
    )


@SHAPES
def test_reviewer_rules_follow_the_step_rules(shape: dict[str, Any]) -> None:
    result = reviewer_call_options(shape, _with_rules(ReviewerOptions(), REVIEWER_RULES))
    assert result["rules_content"] == f"{STEP_RULES}{RULES_SEPARATOR}{REVIEWER_RULES}"


@SHAPES
def test_reviewer_rules_stand_alone_when_the_step_has_none(shape: dict[str, Any]) -> None:
    no_step_rules = {**shape, "rules_content": None}
    result = reviewer_call_options(no_step_rules, _with_rules(ReviewerOptions(), REVIEWER_RULES))
    assert result["rules_content"] == REVIEWER_RULES


@SHAPES
def test_reviewer_without_a_rules_file_keeps_the_step_rules(shape: dict[str, Any]) -> None:
    result = reviewer_call_options(shape, ReviewerOptions(tools=False))
    assert result["rules_content"] == STEP_RULES


@SHAPES
def test_a_rules_file_that_was_never_read_is_refused(shape: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="never read"):
        reviewer_call_options(shape, ReviewerOptions(rules="r.md"))
