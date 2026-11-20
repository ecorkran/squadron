"""Recipe search by name across ordered directories (slice 434, D1)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from squadron.recipes.recipe import RecipeError, load_recipe
from squadron.recipes.recipe_search import (
    PROJECT_RECIPES_DIR,
    find_recipe,
    load_recipes,
    production_recipe_dirs,
    resolve_recipe,
    shipped_recipes_dir,
)


def _recipe(directory: Path, name: str, reviewers: str = "[haiku]", stem: str | None = None) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{stem or name}.yaml"
    path.write_text(f"name: {name}\nreviewers: {reviewers}\n", encoding="utf-8")
    return path


def test_first_match_wins_and_shadowed_name_warns(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    first = _recipe(tmp_path / "project", "r", "[sol]")
    second = _recipe(tmp_path / "shipped", "r", "[luna]")
    with caplog.at_level(logging.WARNING, logger="squadron.recipes.recipe_search"):
        path = resolve_recipe("r", [first.parent, second.parent])
    assert path == first
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert str(first) in warnings[0] and str(second) in warnings[0]


def test_broken_file_found_by_name_raises_with_its_path(tmp_path: Path) -> None:
    broken_dir = tmp_path / "project"
    broken_dir.mkdir()
    broken = broken_dir / "r.yaml"
    broken.write_text("name: r\nreviewers: [a]\nbogus: 1\n", encoding="utf-8")
    good = _recipe(tmp_path / "shipped", "r")
    with pytest.raises(RecipeError) as raised:
        load_recipes(["r"], [broken_dir, good.parent])
    assert raised.value.path == broken
    with pytest.raises(RecipeError):
        find_recipe("r", [broken_dir, good.parent])


def test_name_not_matching_stem_raises(tmp_path: Path) -> None:
    path = _recipe(tmp_path, "other", stem="r")
    with pytest.raises(RecipeError, match="does not match the file name 'r'") as raised:
        load_recipe(path)
    assert raised.value.path == path


def test_unknown_name_lists_known_names(tmp_path: Path) -> None:
    _recipe(tmp_path / "a", "alpha")
    _recipe(tmp_path / "b", "beta")
    with pytest.raises(RecipeError, match="no recipe named 'nope'; known: alpha, beta"):
        resolve_recipe("nope", [tmp_path / "a", tmp_path / "b"])


def test_path_ref_is_returned_as_given(tmp_path: Path) -> None:
    assert resolve_recipe("own.yaml", [tmp_path]) == Path("own.yaml")
    assert resolve_recipe(str(tmp_path / "own"), [tmp_path]) == tmp_path / "own"


def test_find_recipe_returns_none_for_unknown_name(tmp_path: Path) -> None:
    assert find_recipe("nope", [tmp_path, tmp_path / "missing"]) is None
    path = _recipe(tmp_path, "r")
    found = find_recipe("r", [tmp_path])
    assert found is not None and found[1] == path and found[0].name == "r"


def test_production_dirs_are_project_then_shipped(tmp_path: Path) -> None:
    assert production_recipe_dirs(tmp_path) == [tmp_path / PROJECT_RECIPES_DIR, shipped_recipes_dir()]
