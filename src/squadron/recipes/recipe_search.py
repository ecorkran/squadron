"""Find recipe files by name across ordered directories (slice 434, D1).

The caller gives the directories: production searches the project's recipes, then the
shipped ones; ``sq benchmark recall`` searches its reference directory, then the shipped
ones. The first directory holding a name wins; a file found by name that fails to load
raises, and the search never moves on to a later directory.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path

from squadron.data import data_dir
from squadron.recipes.recipe import RECIPE_SUFFIX, Recipe, RecipeError, load_recipe

_logger = logging.getLogger(__name__)

#: Project recipes, relative to the working directory.
PROJECT_RECIPES_DIR = Path("project-documents/user/recipes")
#: Shipped recipes, under the package data directory.
SHIPPED_RECIPES_SUBDIR = "recipes"
_PATH_SUFFIXES = (RECIPE_SUFFIX, ".yml")


def shipped_recipes_dir() -> Path:
    """The directory of recipes shipped with squadron."""
    return data_dir() / SHIPPED_RECIPES_SUBDIR


def production_recipe_dirs(cwd: Path) -> list[Path]:
    """Production search order: the project's recipes, then the shipped ones."""
    return [cwd / PROJECT_RECIPES_DIR, shipped_recipes_dir()]


def is_path_ref(ref: str) -> bool:
    """A ref with a directory part or a YAML suffix names a file, not a recipe."""
    as_path = Path(ref)
    return as_path.suffix in _PATH_SUFFIXES or len(as_path.parts) > 1


def _matches(name: str, search_dirs: Sequence[Path]) -> list[Path]:
    candidates = [d / f"{name}{RECIPE_SUFFIX}" for d in search_dirs]
    return [path for path in candidates if path.is_file()]


def known_recipe_names(search_dirs: Sequence[Path]) -> list[str]:
    """Every recipe name found across *search_dirs*, sorted and unique."""
    return sorted({p.stem for d in search_dirs for p in d.glob(f"*{RECIPE_SUFFIX}")})


def _find_path(name: str, search_dirs: Sequence[Path]) -> Path | None:
    matches = _matches(name, search_dirs)
    if not matches:
        return None
    if len(matches) > 1:
        _logger.warning(
            "recipe %r found in more than one directory; using %s, shadowing %s",
            name,
            matches[0],
            ", ".join(str(m) for m in matches[1:]),
        )
    return matches[0]


def resolve_recipe(ref: str, search_dirs: Sequence[Path]) -> Path:
    """A path ref is returned as given; a name is ``<name>.yaml`` in the first directory
    holding it. No match raises ``RecipeError`` listing the known names."""
    if is_path_ref(ref):
        return Path(ref)
    found = _find_path(ref, search_dirs)
    if found is None:
        known = ", ".join(known_recipe_names(search_dirs)) or "none"
        searched = ", ".join(str(d) for d in search_dirs)
        raise RecipeError(Path(ref), f"no recipe named {ref!r}; known: {known}; searched: {searched}")
    return found


def load_recipes(refs: Sequence[str], search_dirs: Sequence[Path]) -> list[Recipe]:
    """Resolve and load each ref; a file that fails to load raises."""
    return [load_recipe(resolve_recipe(ref, search_dirs)) for ref in refs]


def find_recipe(name: str, search_dirs: Sequence[Path]) -> tuple[Recipe, Path] | None:
    """The recipe named *name* and its file, or ``None`` when no directory holds it.

    Names only (classification never takes a path). A file found that fails to load raises.
    """
    found = _find_path(name, search_dirs)
    if found is None:
        return None
    return load_recipe(found), found
