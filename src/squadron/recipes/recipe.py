"""Recipes (slice 430, D2; moved here in slice 434): reviewers as fan-out or a pool,
then ordered combs.

A recipe file is YAML: ``name``, ``reviewers`` (one entry = a single reviewer), optional
``pool`` (default false) and ``combs`` (default none). Combs run on each reviewer's output
separately, so a recipe needs one review stage per reviewer plus, per reviewer, one comb
stage for each prefix of its comb chain.

Slice 437 adds two optional keys: ``reviewer_options`` (alias to ``tools`` / ``rules``,
D1-D3) and ``keep_categories`` (the category filter, D5).
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from squadron.core.finding_categories import ReviewCategory
from squadron.metrology.recall_run_models import StageKind

RECIPE_SUFFIX = ".yaml"
#: Issue that tracks a recipe with both a category filter and combs.
KEEP_CATEGORIES_COMBS_ISSUE = "#392"
_LOADER_SET_OPTIONS = ("rules_path", "rules_content")


class RecipeError(Exception):
    """A recipe file is unreadable or invalid."""

    def __init__(self, path: Path, reason: str) -> None:
        super().__init__(f"{path}: {reason}")
        self.path = path
        self.reason = reason


class ReviewerOptions(BaseModel):
    """What one reviewer of a recipe is called with beyond its alias (437 D1-D3).

    ``tools`` and ``rules`` (a file name beside the recipe) are written in the recipe
    file; ``rules_path`` and ``rules_content`` are set by ``load_recipe`` after it reads
    the rules file and are refused in the file itself.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    tools: bool = True
    rules: str | None = None
    rules_path: Path | None = None
    rules_content: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _refuse_loader_set(cls, data: object) -> object:
        original = data
        written = cast(dict[str, Any], data) if isinstance(data, dict) else {}
        for key in _LOADER_SET_OPTIONS:
            if key in written:
                raise ValueError(f"{key} is set by the loader and cannot be written in a recipe")
        return original


def rules_sha256(options: ReviewerOptions) -> str | None:
    """sha256 of the reviewer's rules content, ``None`` with no rules: the one place it is hashed."""
    if options.rules_content is None:
        return None
    return hashlib.sha256(options.rules_content.encode("utf-8")).hexdigest()


class Recipe(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    reviewers: tuple[str, ...]
    pool: bool = False
    combs: tuple[str, ...] = ()
    reviewer_options: Mapping[str, ReviewerOptions] = Field(default_factory=dict)
    keep_categories: tuple[ReviewCategory, ...] | None = None

    def __hash__(self) -> int:
        # Explicit: the generated hash fails on the ``reviewer_options`` mapping.
        return hash(
            (
                self.name,
                self.reviewers,
                self.pool,
                self.combs,
                tuple(self.reviewer_options.items()),
                self.keep_categories,
            )
        )

    def reviewers_with_options(self) -> tuple[str, ...]:
        """Reviewers whose options change how they are called; all-default options do not."""
        default = ReviewerOptions()
        return tuple(a for a, options in self.reviewer_options.items() if options != default)

    @field_validator("keep_categories", mode="before")
    @classmethod
    def _known_categories(cls, value: object) -> object:
        # Checked before the enum's own error, which does not carry the offending input.
        original = value
        given = cast(Sequence[Any], value) if isinstance(value, (list, tuple)) else ()
        valid = [category.value for category in ReviewCategory]
        for item in given:
            if item not in valid:
                raise ValueError(f"unknown category {item!r}; valid: {', '.join(valid)}")
        return original

    @model_validator(mode="after")
    def _checks(self) -> Recipe:
        unknown = sorted(set(self.reviewer_options) - set(self.reviewers))
        if unknown:
            raise ValueError(f"reviewer_options names aliases not in reviewers: {unknown}")
        if self.keep_categories is not None and not self.keep_categories:
            raise ValueError("keep_categories is empty; omit it for no filter")
        if self.keep_categories is not None and self.combs:
            raise ValueError(
                f"keep_categories with combs is not supported ({KEEP_CATEGORIES_COMBS_ISSUE})"
            )
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


def _error_reason(error: Any) -> str:
    """A validation error's message, led by its field path when it has one."""
    location = ".".join(str(part) for part in error["loc"])
    return f"{location}: {error['msg']}" if location else str(error["msg"])


def load_recipe(path: Path) -> Recipe:
    """Read and validate one recipe file; any problem raises ``RecipeError``."""
    try:
        raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise RecipeError(path, f"unreadable: {exc}") from exc
    if not isinstance(raw, dict):
        raise RecipeError(path, "not a YAML mapping")
    try:
        recipe = Recipe.model_validate(raw)
    except ValidationError as exc:
        reasons = "; ".join(_error_reason(error) for error in exc.errors())
        raise RecipeError(path, reasons) from exc
    if recipe.name != path.stem:
        raise RecipeError(path, f"name {recipe.name!r} does not match the file name {path.stem!r}")
    return _with_rules_read(path, recipe)


def _read_rules(recipe_path: Path, options: ReviewerOptions) -> ReviewerOptions:
    """*options* with its rules file read from the recipe's own directory (D3)."""
    if options.rules is None:
        return options
    name = options.rules
    if not name or Path(name).name != name or name in (".", ".."):
        raise RecipeError(
            recipe_path, f"rules {name!r} must be a file name beside the recipe, with no directory"
        )
    rules_path = (recipe_path.parent / name).resolve()
    try:
        content = rules_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise RecipeError(recipe_path, f"rules file {name!r} not found at {rules_path}") from exc
    except UnicodeDecodeError as exc:
        raise RecipeError(recipe_path, f"rules file {name!r} is not UTF-8: {exc}") from exc
    except OSError as exc:
        raise RecipeError(recipe_path, f"rules file {name!r} unreadable: {exc}") from exc
    if not content.strip():
        raise RecipeError(recipe_path, f"rules file {name!r} is empty")
    return options.model_copy(update={"rules_path": rules_path, "rules_content": content})


def _with_rules_read(path: Path, recipe: Recipe) -> Recipe:
    if all(options.rules is None for options in recipe.reviewer_options.values()):
        return recipe
    read = {alias: _read_rules(path, options) for alias, options in recipe.reviewer_options.items()}
    return recipe.model_copy(update={"reviewer_options": read})


def required_stages(recipe: Recipe) -> tuple[RequiredStage, ...]:
    """Per reviewer: its review stage, then one comb stage per chain prefix, in order."""
    stages: list[RequiredStage] = []
    for reviewer in recipe.reviewers:
        stages.append(RequiredStage(StageKind.REVIEW, reviewer, ()))
        for depth in range(1, len(recipe.combs) + 1):
            stages.append(RequiredStage(StageKind.COMB, reviewer, recipe.combs[:depth]))
    return tuple(stages)
