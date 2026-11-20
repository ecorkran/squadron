"""Shared recipe review fixtures (slice 434): test aliases, the recipe file, a defect repo."""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.core.models import Effort
from squadron.models import aliases
from squadron.models.aliases import ModelAlias
from squadron.recipes.recipe import Recipe, load_recipe
from tests.recipes.support import COMBS, RECIPE_NAME, RECIPE_TEXT, REVIEWERS, defect_repo

RECIPE_ALIASES: dict[str, ModelAlias] = {
    alias: {"profile": "openrouter", "model": f"vendor/{alias}"} for alias in (*REVIEWERS, *COMBS)
}
RECIPE_ALIASES[REVIEWERS[0]]["effort"] = Effort.high


@pytest.fixture
def recipe_aliases(monkeypatch: pytest.MonkeyPatch) -> dict[str, ModelAlias]:
    """The recipe's member aliases, on top of the built-in registry."""
    monkeypatch.setattr(aliases, "load_user_aliases", lambda: dict(RECIPE_ALIASES))
    return RECIPE_ALIASES


@pytest.fixture
def recipe_file(tmp_path: Path) -> Path:
    path = tmp_path / "recipes" / f"{RECIPE_NAME}.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(RECIPE_TEXT, encoding="utf-8")
    return path


@pytest.fixture
def recipe(recipe_file: Path, recipe_aliases: dict[str, ModelAlias]) -> Recipe:
    return load_recipe(recipe_file)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return defect_repo(tmp_path / "repo")
