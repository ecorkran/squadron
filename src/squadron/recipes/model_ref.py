"""One classification of a review model name: alias or recipe (slice 434, D2).

``classify_review_model`` decides which review path runs; callers ``match`` on the
returned type, never on the name. ``validate_recipe_review`` holds the recipe refusals,
called right after classification at each site, because the pre-run check and the review
execution know different inputs.
"""

from __future__ import annotations

import difflib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from squadron.models.aliases import (
    UnknownModelAliasError,
    get_all_aliases,
    require_known_model,
)
from squadron.recipes.recipe import Recipe, RecipeError
from squadron.recipes.recipe_search import find_recipe, known_recipe_names
from squadron.review.templates import ReviewTemplate

_CLOSE_MATCHES = 3
#: The template input a comb needs: combs are written for a code change (D4).
DIFF_INPUT = "diff"
#: Refusals for a review with no diff input (437 D7); ``{template}`` is the template name.
KEEP_CATEGORIES_NO_DIFF = (
    "keep_categories is the code review's category filter and needs a diff; "
    "template '{template}' has no diff input here"
)
NO_TOOLS_REVIEWER_NO_DIFF = (
    "reviewer '{reviewer}' has tools: false and would get only the prompt; it needs a diff, "
    "and template '{template}' has no diff input here"
)


class ReviewModelError(ValueError):
    """A review model name that cannot run: unknown, ambiguous, or a refused recipe."""


@dataclass(frozen=True)
class AliasRef:
    """A model alias, or a literal model id with a profile source: a single-model review."""

    name: str


@dataclass(frozen=True)
class RecipeRef:
    """A recipe found by the production search: a recipe review."""

    recipe: Recipe
    path: Path


ReviewModelRef = AliasRef | RecipeRef


def _is_known_model(name: str) -> bool:
    aliases = get_all_aliases()
    return name in aliases or any(alias["model"] == name for alias in aliases.values())


def _unknown_message(name: str, search_dirs: Sequence[Path]) -> str:
    close = difflib.get_close_matches(name, list(get_all_aliases()), n=_CLOSE_MATCHES)
    recipes = ", ".join(known_recipe_names(search_dirs)) or "none"
    return f"{UnknownModelAliasError(name, close)} Known recipes: {recipes}."


def classify_review_model(
    name: str, *, profile_source: bool, search_dirs: Sequence[Path]
) -> ReviewModelRef:
    """``AliasRef`` for a known model (or a literal id with a profile source),
    ``RecipeRef`` for a recipe; a name that is both or neither raises ``ReviewModelError``."""
    try:
        found = find_recipe(name, search_dirs)
    except RecipeError as exc:
        raise ReviewModelError(f"recipe '{name}' cannot be loaded: {exc}") from exc
    known_model = _is_known_model(name)
    if found is not None and known_model:
        raise ReviewModelError(
            f"'{name}' is a model alias and a recipe ({found[1]}); rename the recipe"
        )
    if found is not None:
        return RecipeRef(recipe=found[0], path=found[1])
    try:
        require_known_model(name, profile_source=profile_source)
    except UnknownModelAliasError as exc:
        raise ReviewModelError(_unknown_message(name, search_dirs)) from exc
    return AliasRef(name)


def template_takes_diff(template: ReviewTemplate) -> bool:
    """Whether *template* declares a ``diff`` input (required or optional)."""
    return any(i.name == DIFF_INPUT for i in (*template.required_inputs, *template.optional_inputs))


def _refuse(recipe: Recipe, reason: str) -> ReviewModelError:
    return ReviewModelError(f"recipe '{recipe.name}': {reason}")


def check_recipe_members(recipe: Recipe) -> None:
    """Every reviewer and comb alias must pass ``require_known_model``; else raise naming it."""
    for role, members in (("reviewer", recipe.reviewers), ("comb", recipe.combs)):
        for alias in members:
            try:
                require_known_model(alias, profile_source=False)
            except UnknownModelAliasError as exc:
                raise _refuse(recipe, f"{role} '{alias}': {exc}") from exc


def _refuse_without_diff_inputs(recipe: Recipe, template: ReviewTemplate, has_diff: bool) -> None:
    """The filter and a no-tools reviewer only make sense on a review that has a diff (D7)."""
    if has_diff:
        return
    if recipe.keep_categories is not None:
        raise _refuse(recipe, KEEP_CATEGORIES_NO_DIFF.format(template=template.name))
    for reviewer, options in recipe.reviewer_options.items():
        if not options.tools:
            raise _refuse(
                recipe, NO_TOOLS_REVIEWER_NO_DIFF.format(reviewer=reviewer, template=template.name)
            )


def validate_recipe_review(
    ref: RecipeRef,
    *,
    template: ReviewTemplate,
    has_diff: bool,
    explicit_profile: str | None,
    no_tools: bool,
) -> None:
    """Raise ``ReviewModelError`` naming the recipe and member when the recipe cannot run
    as this review: unknown member alias, ``pool: true``, judge template, combs, a category
    filter or a no-tools reviewer with no diff, an explicit profile, or a tool-less review."""
    recipe = ref.recipe
    check_recipe_members(recipe)
    if recipe.pool:
        raise _refuse(
            recipe,
            "pool: true is refused in a review; a random reviewer pick could change "
            "the verdict between revise rounds",
        )
    if template.is_judge:
        raise _refuse(recipe, f"template '{template.name}' is a judge template; recipes are refused")
    if recipe.combs and not has_diff:
        raise _refuse(
            recipe,
            f"comb '{recipe.combs[0]}' needs a diff; template '{template.name}' has no diff input here",
        )
    _refuse_without_diff_inputs(recipe, template, has_diff)
    if explicit_profile is not None:
        raise _refuse(
            recipe,
            f"profile '{explicit_profile}' is refused; each stage's alias decides its profile",
        )
    if no_tools:
        # Combs always get read tools and a reviewer's provider may bring its own, so a
        # tool-less recipe review cannot be honored for every stage.
        raise _refuse(recipe, "a tool-less review (allowed_tools: [] or --no-tools) is refused")


def resolve_review_model_ref(
    name: str,
    *,
    profile_source: bool,
    search_dirs: Sequence[Path],
    template: ReviewTemplate | None,
    has_diff: bool,
    explicit_profile: str | None,
    no_tools: bool,
) -> ReviewModelRef:
    """The one entry point every site uses: classify *name*, then refuse a recipe that
    cannot run as this review. With no *template* (it is not known yet, or a placeholder),
    only the recipe's member aliases are checked."""
    ref = classify_review_model(name, profile_source=profile_source, search_dirs=search_dirs)
    if isinstance(ref, RecipeRef):
        if template is None:
            check_recipe_members(ref.recipe)
        else:
            validate_recipe_review(
                ref,
                template=template,
                has_diff=has_diff,
                explicit_profile=explicit_profile,
                no_tools=no_tools,
            )
    return ref
