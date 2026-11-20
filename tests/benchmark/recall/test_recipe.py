"""Recall recipes and the committed recipe files (slice 430, D2, D11)."""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.benchmark.recall.recipe_dirs import benchmark_recipe_dirs
from squadron.metrology.recall_run_models import StageKind
from squadron.recipes.recipe import (
    RecipeError,
    RequiredStage,
    load_recipe,
    required_stages,
)
from squadron.recipes.recipe_search import resolve_recipe, shipped_recipes_dir

REPO_ROOT = Path(__file__).resolve().parents[3]
RECIPES_DIR = REPO_ROOT / "project-documents" / "user" / "reference" / "review-recall-recipes"
SHIPPED_DIR = shipped_recipes_dir()
COMMITTED = {
    "haiku-xhigh",
    "sol",
    "sonnet-high",
    "sonnet",
    "luna",
    "haiku-sol-pool",
    "haiku-mimo-opus",
    "haiku-opus",
}


def _write(tmp_path: Path, text: str, stem: str = "r") -> Path:
    path = tmp_path / f"{stem}.yaml"
    path.write_text(text, encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("name: r\nreviewers: []\n", "at least one reviewer"),
        ("name: r\nreviewers: [sol]\npool: true\n", "at least two reviewers"),
        ("name: r\nreviewers: [sol, sol]\n", "duplicate reviewers"),
        ("name: r\nreviewers: [sol]\nextra: 1\n", "Extra inputs"),
        ("- not a mapping\n", "not a YAML mapping"),
        ("name: [unclosed\n", "unreadable"),
    ],
)
def test_loader_refusals(tmp_path: Path, text: str, reason: str) -> None:
    with pytest.raises(RecipeError, match=reason):
        load_recipe(_write(tmp_path, text))


def test_single_reviewer_defaults(tmp_path: Path) -> None:
    recipe = load_recipe(_write(tmp_path, "name: sol\nreviewers: [sol]\n", "sol"))
    assert (recipe.pool, recipe.combs) == (False, ())
    assert required_stages(recipe) == (RequiredStage(StageKind.REVIEW, "sol", ()),)


def test_fan_out_with_two_stage_comb_expands_per_reviewer(tmp_path: Path) -> None:
    text = "name: r\nreviewers: [haiku-xhigh, sol]\ncombs: [luna-r, opus-high]\n"
    stages = required_stages(load_recipe(_write(tmp_path, text)))
    expected = [
        RequiredStage(StageKind.REVIEW, reviewer, chain)
        if not chain
        else RequiredStage(StageKind.COMB, reviewer, chain)
        for reviewer in ("haiku-xhigh", "sol")
        for chain in ((), ("luna-r",), ("luna-r", "opus-high"))
    ]
    assert list(stages) == expected


def test_every_committed_recipe_loads() -> None:
    files = {path.stem: path for path in RECIPES_DIR.glob("*.yaml")}
    assert set(files) == COMMITTED
    for stem, path in files.items():
        assert load_recipe(path).name == stem


def test_d11_recipe_is_fan_out_then_luna_r_then_opus_high() -> None:
    recipe = load_recipe(SHIPPED_DIR / "haiku-sol-luna-opus.yaml")
    assert (recipe.reviewers, recipe.pool, recipe.combs) == (
        ("haiku-xhigh", "sol"),
        False,
        ("luna-r", "opus-high"),
    )


def test_recipe_name_resolves_to_committed_file() -> None:
    assert (
        resolve_recipe("haiku-sol-opus", benchmark_recipe_dirs(REPO_ROOT))
        == SHIPPED_DIR / "haiku-sol-opus.yaml"
    )
    assert load_recipe(
        resolve_recipe("haiku-solr-luna-opus", benchmark_recipe_dirs(REPO_ROOT))
    ).reviewers == (
        "haiku-xhigh",
        "sol-r",
    )


def test_recipe_ref_with_path_or_suffix_is_used_as_given(tmp_path: Path) -> None:
    assert resolve_recipe("own.yaml", benchmark_recipe_dirs(REPO_ROOT)) == Path("own.yaml")
    assert resolve_recipe(str(tmp_path / "own"), benchmark_recipe_dirs(REPO_ROOT)) == tmp_path / "own"


def test_unknown_recipe_name_lists_known_names() -> None:
    with pytest.raises(RecipeError, match="no recipe named 'nope'; known: .*haiku-sol-opus"):
        resolve_recipe("nope", benchmark_recipe_dirs(REPO_ROOT))
