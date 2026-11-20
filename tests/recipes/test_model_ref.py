"""Classifying a review model name as alias or recipe, and the recipe refusals (slice 434, D2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.models import aliases
from squadron.models.aliases import ModelAlias
from squadron.recipes.model_ref import (
    AliasRef,
    RecipeRef,
    ReviewModelError,
    classify_review_model,
    resolve_review_model_ref,
    validate_recipe_review,
)
from squadron.recipes.recipe_search import production_recipe_dirs
from squadron.recipes.stage_config import builtin_template

REPO_ROOT = Path(__file__).resolve().parents[2]
#: The real alias loaders, kept before the autouse fixture patches them.
REAL_BUILTIN_ALIASES = aliases.load_builtin_aliases
REAL_USER_ALIASES = aliases.load_user_aliases
TEST_ALIASES: dict[str, ModelAlias] = {
    "rev-a": {"profile": "openrouter", "model": "vendor/a"},
    "rev-b": {"profile": "openrouter", "model": "vendor/b"},
    "comb-1": {"profile": "openrouter", "model": "vendor/c"},
}


@pytest.fixture(autouse=True)
def test_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(aliases, "load_builtin_aliases", lambda: dict(TEST_ALIASES))
    monkeypatch.setattr(aliases, "load_user_aliases", lambda: {})


def _write(directory: Path, name: str, body: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.yaml"
    path.write_text(f"name: {name}\n{body}", encoding="utf-8")
    return path


@pytest.fixture
def dirs(tmp_path: Path) -> list[Path]:
    project = tmp_path / "project"
    _write(project, "duo", "reviewers: [rev-a, rev-b]\ncombs: [comb-1]\n")
    _write(project, "fan", "reviewers: [rev-a, rev-b]\n")
    _write(project, "pooled", "reviewers: [rev-a, rev-b]\npool: true\n")
    _write(project, "ghost", "reviewers: [rev-a]\ncombs: [no-such-comb]\n")
    _write(project, "rev-b", "reviewers: [rev-a]\n")
    return [project, tmp_path / "shipped"]


def _ref(name: str, dirs: list[Path]) -> RecipeRef:
    ref = classify_review_model(name, profile_source=False, search_dirs=dirs)
    assert isinstance(ref, RecipeRef)
    return ref


def test_alias_classifies_as_alias_ref(dirs: list[Path]) -> None:
    assert classify_review_model("rev-a", profile_source=False, search_dirs=dirs) == AliasRef("rev-a")


def test_literal_model_id_with_profile_source_is_alias_ref(dirs: list[Path]) -> None:
    ref = classify_review_model("vendor/unlisted", profile_source=True, search_dirs=dirs)
    assert ref == AliasRef("vendor/unlisted")


def test_recipe_classifies_as_recipe_ref(dirs: list[Path]) -> None:
    ref = _ref("duo", dirs)
    assert ref.recipe.reviewers == ("rev-a", "rev-b") and ref.path == dirs[0] / "duo.yaml"


def test_name_that_is_both_raises_the_collision_message(dirs: list[Path]) -> None:
    with pytest.raises(ReviewModelError, match="'rev-b' is a model alias and a recipe"):
        classify_review_model("rev-b", profile_source=False, search_dirs=dirs)


def test_name_that_is_neither_lists_close_aliases_and_recipes(dirs: list[Path]) -> None:
    with pytest.raises(ReviewModelError) as raised:
        classify_review_model("rev-c", profile_source=False, search_dirs=dirs)
    message = str(raised.value)
    assert "unknown model alias 'rev-c'" in message and "rev-a" in message
    assert "Known recipes: duo, fan, ghost, pooled, rev-b." in message


@pytest.mark.parametrize(
    ("name", "template", "has_diff", "profile", "no_tools", "member"),
    [
        ("ghost", "code", True, None, False, "no-such-comb"),
        ("pooled", "code", True, None, False, "pool: true"),
        ("fan", "judge-slice-vs-arch", True, None, False, "judge template"),
        ("duo", "slice", False, None, False, "comb-1"),
        ("fan", "code", True, "openrouter", False, "openrouter"),
        ("fan", "code", True, None, True, "tool-less review"),
    ],
)
def test_each_refusal_names_the_recipe_and_member(
    dirs: list[Path],
    name: str,
    template: str,
    has_diff: bool,
    profile: str | None,
    no_tools: bool,
    member: str,
) -> None:
    with pytest.raises(ReviewModelError) as raised:
        resolve_review_model_ref(
            name,
            profile_source=False,
            search_dirs=dirs,
            template=builtin_template(template),
            has_diff=has_diff,
            explicit_profile=profile,
            no_tools=no_tools,
        )
    assert f"recipe '{name}'" in str(raised.value) and member in str(raised.value)


def test_valid_recipe_passes(dirs: list[Path]) -> None:
    validate_recipe_review(
        _ref("duo", dirs),
        template=builtin_template("code"),
        has_diff=True,
        explicit_profile=None,
        no_tools=False,
    )
    validate_recipe_review(
        _ref("fan", dirs),
        template=builtin_template("slice"),
        has_diff=False,
        explicit_profile=None,
        no_tools=False,
    )


def test_without_a_template_only_members_are_checked(dirs: list[Path]) -> None:
    ref = resolve_review_model_ref(
        "pooled",
        profile_source=False,
        search_dirs=dirs,
        template=None,
        has_diff=False,
        explicit_profile=None,
        no_tools=False,
    )
    assert isinstance(ref, RecipeRef)
    with pytest.raises(ReviewModelError, match="no-such-comb"):
        resolve_review_model_ref(
            "ghost",
            profile_source=False,
            search_dirs=dirs,
            template=None,
            has_diff=False,
            explicit_profile=None,
            no_tools=False,
        )


def test_haiku_xhigh_is_an_alias_in_squadrons_own_checkout(monkeypatch: pytest.MonkeyPatch) -> None:
    # Only this test's alias patch is replaced, by the loaders captured at import.
    monkeypatch.setattr(aliases, "load_builtin_aliases", REAL_BUILTIN_ALIASES)
    monkeypatch.setattr(aliases, "load_user_aliases", REAL_USER_ALIASES)
    ref = classify_review_model(
        "haiku-xhigh", profile_source=False, search_dirs=production_recipe_dirs(REPO_ROOT)
    )
    assert ref == AliasRef("haiku-xhigh")
