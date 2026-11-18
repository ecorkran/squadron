"""Recall recipes (slice 430, D2): reviewers as fan-out or a pool, then ordered combs.

A recipe file is YAML: ``name``, ``reviewers`` (one entry = a single reviewer), optional
``pool`` (default false) and ``combs`` (default none). Combs run on each reviewer's output
separately, so a recipe needs one review stage per reviewer plus, per reviewer, one comb
stage for each prefix of its comb chain.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from squadron.metrology.recall_run_models import StageKind

#: Where a recipe named without a path lives, relative to the repository root.
RECIPES_DIR = Path("project-documents/user/reference/review-recall-recipes")
RECIPE_SUFFIX = ".yaml"


class RecipeError(Exception):
    """A recipe file is unreadable or invalid."""

    def __init__(self, path: Path, reason: str) -> None:
        super().__init__(f"{path}: {reason}")
        self.path = path
        self.reason = reason


class Recipe(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    reviewers: tuple[str, ...]
    pool: bool = False
    combs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _checks(self) -> Recipe:
        if not self.reviewers:
            raise ValueError("a recipe needs at least one reviewer")
        if len(set(self.reviewers)) != len(self.reviewers):
            raise ValueError(f"duplicate reviewers: {list(self.reviewers)}")
        if self.pool and len(self.reviewers) < 2:
            raise ValueError("pool: true needs at least two reviewers")
        return self


@dataclass(frozen=True)
class RequiredStage:
    """One stage a recipe needs per case run; ``chain`` is empty for a review."""

    kind: StageKind
    reviewer: str
    chain: tuple[str, ...]


def load_recipe(path: Path) -> Recipe:
    """Read and validate one recipe file; any problem raises ``RecipeError``."""
    try:
        raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise RecipeError(path, f"unreadable: {exc}") from exc
    if not isinstance(raw, dict):
        raise RecipeError(path, "not a YAML mapping")
    try:
        return Recipe.model_validate(raw)
    except ValidationError as exc:
        reasons = "; ".join(error["msg"] for error in exc.errors())
        raise RecipeError(path, reasons) from exc


def resolve_recipe(ref: str, repo_root: Path) -> Path:
    """A recipe name (``haiku-sol-opus``) maps to its file in ``RECIPES_DIR``; a ref with a
    directory part or a YAML suffix is a path as given. An unknown name lists the known ones."""
    as_path = Path(ref)
    if as_path.suffix in (RECIPE_SUFFIX, ".yml") or len(as_path.parts) > 1:
        return as_path
    recipes_dir = repo_root / RECIPES_DIR
    path = recipes_dir / f"{ref}{RECIPE_SUFFIX}"
    if not path.is_file():
        known = sorted(p.stem for p in recipes_dir.glob(f"*{RECIPE_SUFFIX}"))
        raise RecipeError(path, f"no recipe named {ref!r}; known: {', '.join(known) or 'none'}")
    return path


def load_recipes(refs: list[str], repo_root: Path) -> list[Recipe]:
    """Resolve and load each recipe ref (a name or a path)."""
    return [load_recipe(resolve_recipe(ref, repo_root)) for ref in refs]


def required_stages(recipe: Recipe) -> tuple[RequiredStage, ...]:
    """Per reviewer: its review stage, then one comb stage per chain prefix, in order."""
    stages: list[RequiredStage] = []
    for reviewer in recipe.reviewers:
        stages.append(RequiredStage(StageKind.REVIEW, reviewer, ()))
        for depth in range(1, len(recipe.combs) + 1):
            stages.append(RequiredStage(StageKind.COMB, reviewer, recipe.combs[:depth]))
    return tuple(stages)
