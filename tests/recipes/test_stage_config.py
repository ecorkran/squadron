"""Stage identity for recipe review stages (slice 434, D8)."""

from __future__ import annotations

import pytest

from squadron.core.models import Effort
from squadron.metrology.recall_run_models import StageKind
from squadron.models import aliases
from squadron.models.aliases import ModelAlias
from squadron.recipes.recipe import Recipe, required_stages
from squadron.recipes.stage_config import (
    COMB_TEMPLATE_NAME,
    StageConfigError,
    alias_stage_config,
    builtin_template_hash,
    planned_stages,
    stage_alias,
)

REVIEW_HASH = "review-template-hash"
TEST_ALIASES: dict[str, ModelAlias] = {
    "rev-a": {"profile": "openrouter", "model": "vendor/a", "effort": Effort.high},
    "rev-b": {"profile": "openrouter", "model": "vendor/b"},
    "comb-1": {"profile": "openrouter", "model": "vendor/c", "tool_use": False},
    "comb-2": {"profile": "openrouter", "model": "vendor/d", "max_output_tokens": 4096},
}


@pytest.fixture(autouse=True)
def test_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(aliases, "load_user_aliases", lambda: dict(TEST_ALIASES))


def test_review_and_comb_hash_give_different_config_keys() -> None:
    comb_hash = builtin_template_hash(COMB_TEMPLATE_NAME)
    as_review = alias_stage_config("rev-a", REVIEW_HASH)
    as_comb = alias_stage_config("rev-a", comb_hash)
    assert as_review.config_key != as_comb.config_key
    assert as_review.template_hash == REVIEW_HASH and as_comb.template_hash == comb_hash


def test_tool_use_and_max_output_tokens_come_from_the_alias() -> None:
    no_tools = alias_stage_config("comb-1", REVIEW_HASH)
    capped = alias_stage_config("comb-2", REVIEW_HASH)
    assert (no_tools.tool_use, no_tools.max_output_tokens) == (False, None)
    assert (capped.tool_use, capped.max_output_tokens) == (True, 4096)
    assert (capped.model, capped.profile) == ("vendor/d", "openrouter")


def test_alias_with_no_profile_raises() -> None:
    with pytest.raises(StageConfigError, match="no-such-alias"):
        alias_stage_config("no-such-alias", REVIEW_HASH)


def test_planned_stages_follow_required_stages_order() -> None:
    recipe = Recipe(name="r", reviewers=("rev-a", "rev-b"), combs=("comb-1", "comb-2"))
    comb_hash = builtin_template_hash(COMB_TEMPLATE_NAME)
    planned = planned_stages(recipe, REVIEW_HASH)
    stages = required_stages(recipe)
    assert len(planned) == 6
    for stage, config in zip(stages, planned, strict=True):
        expected = comb_hash if stage.kind is StageKind.COMB else REVIEW_HASH
        assert config.template_hash == expected
        assert config == alias_stage_config(stage_alias(stage), expected)
    assert [stage_alias(s) for s in stages] == [
        "rev-a", "comb-1", "comb-2", "rev-b", "comb-1", "comb-2",
    ]  # fmt: skip
