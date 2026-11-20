"""Live stage identity from the alias registry (slice 430 D4)."""

from __future__ import annotations

import dataclasses

import pytest

from squadron.benchmark.recall.scoring import recipe_outputs
from squadron.benchmark.recall.stage_identity import (
    LiveStageResolver,
    StageIdentityError,
    live_stage_config,
)
from squadron.core.models import Effort
from squadron.data import data_dir
from squadron.metrology.identity import template_behavior_hash, template_content_hash
from squadron.metrology.recall_run_models import (
    LIVE_SOURCE,
    RecallLeakVerdict,
    StageEntry,
    StageKind,
    StageOutcome,
    entry_key,
)
from squadron.models import aliases
from squadron.models.aliases import ModelAlias
from squadron.pipeline.usage_capture import effort_sent_by_profile
from squadron.recipes.recipe import Recipe
from squadron.review import templates
from squadron.review.templates import load_template
from tests.benchmark.recall.scoring_support import finding, make_case, make_run
from tests.benchmark.recall.support import FIXED_NOW

TWINS: dict[str, ModelAlias] = {
    "twin-a": {"profile": "openrouter", "model": "vendor/model-x", "effort": Effort.high},
    "twin-b": {"profile": "openrouter", "model": "vendor/model-x", "effort": Effort.high},
    "twin-low": {"profile": "openrouter", "model": "vendor/model-x", "effort": Effort.low},
}


@pytest.fixture(autouse=True)
def twin_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(aliases, "load_user_aliases", lambda: dict(TWINS))


def test_aliases_with_the_same_settings_share_a_config_key() -> None:
    config_a, effort_a = live_stage_config("twin-a", StageKind.REVIEW)
    config_b, _ = live_stage_config("twin-b", StageKind.REVIEW)
    assert config_a.config_key == config_b.config_key
    assert config_a.model == "vendor/model-x" and config_a.profile == "openrouter"
    assert config_a.tool_use is True and config_a.max_output_tokens is None
    assert effort_a is Effort.high


def test_different_configured_effort_gives_different_entry_keys() -> None:
    config_a, effort_a = live_stage_config("twin-a", StageKind.REVIEW)
    config_low, effort_low = live_stage_config("twin-low", StageKind.REVIEW)
    assert config_a.config_key == config_low.config_key
    assert entry_key(config_a, effort_a) != entry_key(config_low, effort_low)


def test_review_and_comb_templates_differ() -> None:
    review, _ = live_stage_config("twin-a", StageKind.REVIEW)
    comb, _ = live_stage_config("twin-a", StageKind.COMB)
    assert review.template_hash != comb.template_hash


def test_unknown_alias_raises_naming_it() -> None:
    with pytest.raises(StageIdentityError, match="no-such-alias"):
        live_stage_config("no-such-alias", StageKind.REVIEW)
    assert LiveStageResolver().resolve("no-such-alias", StageKind.REVIEW) is None


def test_report_scores_alias_a_entry_for_a_recipe_naming_alias_b() -> None:
    case = make_case()
    config, effort = live_stage_config("twin-a", StageKind.REVIEW)
    entry = StageEntry(
        kind=StageKind.REVIEW,
        config=config,
        effort_configured=effort,
        effort_sent=effort_sent_by_profile("openrouter", effort),
        findings=(finding(1, "src/a.py"),),
        outcome=StageOutcome.OK,
        leak=RecallLeakVerdict.CONFINED,
        source=LIVE_SOURCE,
        case_set="s@v1",
        alias="twin-a",
        created=FIXED_NOW,
    )
    runs = {(case.case_id, 1): make_run(case, 1, entry)}
    rows = recipe_outputs(
        Recipe(name="b", reviewers=("twin-b",)), [case], runs, [1], LiveStageResolver()
    )
    assert len(rows) == 1 and len(rows[0].pairs) == 1 and not rows[0].left_out


def test_template_hash_is_the_builtin_the_scrubbed_call_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    builtin = load_template(data_dir() / "templates" / "code.yaml")
    override = dataclasses.replace(builtin, system_prompt="a user override of the code template")
    monkeypatch.setattr(templates, "get_template", lambda name: override)
    assert template_content_hash("code") != template_behavior_hash(builtin)
    config, _ = live_stage_config("twin-a", StageKind.REVIEW)
    assert config.template_hash == template_behavior_hash(builtin)
