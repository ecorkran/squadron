"""Stage identity for recipe review stages (slice 434, D8)."""

from __future__ import annotations

import pytest

from squadron.core.models import Effort
from squadron.metrology.recall_run_models import StageConfig, StageKind
from squadron.models import aliases
from squadron.models.aliases import ModelAlias
from squadron.recipes.recipe import Recipe, ReviewerOptions, required_stages, rules_sha256
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


def _with_rules(content: str | None) -> ReviewerOptions:
    options = ReviewerOptions(rules=None if content is None else "r.md")
    return options.model_copy(update={"rules_content": content})


def test_no_options_gives_the_same_config_as_before() -> None:
    plain = alias_stage_config("rev-a", REVIEW_HASH)
    assert plain.rules_hash is None
    assert alias_stage_config("rev-a", REVIEW_HASH, ReviewerOptions()) == plain
    assert alias_stage_config("rev-a", REVIEW_HASH, ReviewerOptions()).config_key == plain.config_key


def test_stored_config_without_rules_hash_loads_and_keeps_its_key() -> None:
    stored = alias_stage_config("rev-a", REVIEW_HASH)
    payload = stored.model_dump(mode="json")
    del payload["rules_hash"]
    loaded = StageConfig.model_validate(payload)
    assert loaded.rules_hash is None
    assert loaded.config_key == stored.config_key


def test_rules_content_and_tools_change_the_key() -> None:
    plain = alias_stage_config("rev-a", REVIEW_HASH)
    one = alias_stage_config("rev-a", REVIEW_HASH, _with_rules("one"))
    two = alias_stage_config("rev-a", REVIEW_HASH, _with_rules("two"))
    assert len({plain.config_key, one.config_key, two.config_key}) == 3
    no_tools = alias_stage_config("rev-a", REVIEW_HASH, ReviewerOptions(tools=False))
    assert no_tools.tool_use is False and plain.tool_use is True
    assert no_tools.config_key != plain.config_key


def test_planned_stages_apply_options_to_that_reviewers_stage_only() -> None:
    options = _with_rules("line pass rules").model_copy(update={"tools": False})
    recipe = Recipe(name="r", reviewers=("rev-a", "rev-b"), reviewer_options={"rev-b": options})
    first, second = planned_stages(recipe, REVIEW_HASH)
    assert first == alias_stage_config("rev-a", REVIEW_HASH)
    assert second.tool_use is False
    assert second.rules_hash == rules_sha256(options)
