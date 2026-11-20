"""The ``recipes/`` package's import boundary (slice 434, Architecture).

``recipes/`` sits above ``review/`` and ``metrology/`` and below ``pipeline/``, ``cli/``
and ``benchmark/``. An import against that direction would create a cycle.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "squadron"
RECIPES_FORBIDDEN = ("squadron.pipeline", "squadron.cli", "squadron.benchmark")
BELOW_RECIPES = ("review", "metrology")


def _imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.append(node.module)
    return names


def _violations(package_dir: Path, forbidden: tuple[str, ...]) -> list[str]:
    found: list[str] = []
    for path in sorted(package_dir.rglob("*.py")):
        for module in _imported_modules(path):
            if any(module == f or module.startswith(f"{f}.") for f in forbidden):
                found.append(f"{path.relative_to(SRC)} imports {module}")
    return found


def test_recipes_imports_nothing_above_it() -> None:
    assert _violations(SRC / "recipes", RECIPES_FORBIDDEN) == []


@pytest.mark.parametrize("package", BELOW_RECIPES)
def test_lower_packages_do_not_import_recipes(package: str) -> None:
    assert _violations(SRC / package, ("squadron.recipes",)) == []
