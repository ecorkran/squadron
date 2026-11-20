"""Where ``sq benchmark recall`` looks for a recipe named without a path (slice 430 D2, 434 D1)."""

from __future__ import annotations

from pathlib import Path

from squadron.recipes.recipe_search import shipped_recipes_dir

#: The benchmark's reference recipes, relative to the repository root.
RECIPES_DIR = Path("project-documents/user/reference/review-recall-recipes")


def benchmark_recipe_dirs(repo_root: Path) -> list[Path]:
    """Benchmark search order: the reference recipes, then the shipped ones."""
    return [repo_root / RECIPES_DIR, shipped_recipes_dir()]
