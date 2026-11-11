"""Resolve a project's packaging boundary (slice 422 D6).

Run as a script under the parent sandbox's interpreter: ``python boundary_resolver.py CONFIG``,
where CONFIG is a JSON file ``{"name": <distribution name or null>, "scripts": ["mod:attr", ...]}``
written by the harness (which has ``tomllib``; this script must run on any project Python).
Prints one JSON object ``{"allowed": [[module, qualname], ...]}`` on stdout.

Allowed entries are each script target and each name in a top-level package's ``__all__``,
resolved to its defining ``(module, qualname)``. Only a top-level ``__all__`` counts:
internal modules often define one for star-import hygiene, which is not a packaging
declaration.

A distribution's top-level packages come from its installed files, plus, for an editable
install, the directories its ``.pth`` file adds to ``sys.path``: ``packages_distributions()``
finds nothing for an editable install, which is what ``uv sync`` makes.

Exits ``IMPORT_FAILURE_EXIT`` when a package or script target will not import (the boundary
is undecidable, not the harness's fault); any other failure exits with Python's default
code. The harness repeats ``IMPORT_FAILURE_EXIT`` because it cannot import this script.
"""

from __future__ import annotations

import importlib
import importlib.metadata
import json
import os
import sys
import traceback
from typing import Any

IMPORT_FAILURE_EXIT = 3
_SKIPPED_NAMES = frozenset({"__pycache__"})


def _is_importable_name(name: str) -> bool:
    return name.isidentifier() and name not in _SKIPPED_NAMES


def _names_from_files(dist: Any) -> set[str]:
    """Top-level names a regular install put in site-packages."""
    names: set[str] = set()
    for file in dist.files or ():
        parts = file.parts
        if not parts or parts[0] in ("..", "") or parts[0].endswith((".dist-info", ".egg-info")):
            continue
        if len(parts) > 1:
            names.add(parts[0])
        elif parts[0].endswith(".py"):
            names.add(parts[0][: -len(".py")])
    return {name for name in names if _is_importable_name(name)}


def _names_from_editable_paths(dist: Any) -> set[str]:
    """Top-level packages and modules in the directories an editable ``.pth`` adds."""
    names: set[str] = set()
    for file in dist.files or ():
        if not str(file).endswith(".pth"):
            continue
        text: str = dist.locate_file(file).read_text(encoding="utf-8")
        for line in text.splitlines():
            directory = line.strip()
            if not directory or directory.startswith(("#", "import ")) or not os.path.isdir(directory):
                continue
            for entry in os.listdir(directory):
                full = os.path.join(directory, entry)
                if os.path.isdir(full) and os.path.exists(os.path.join(full, "__init__.py")):
                    names.add(entry)
                elif entry.endswith(".py"):
                    names.add(entry[: -len(".py")])
    return {name for name in names if _is_importable_name(name)}


def top_level_packages(dist: Any) -> list[str]:
    """Sorted top-level importable names the distribution provides."""
    return sorted(_names_from_files(dist) | _names_from_editable_paths(dist))


def _qualified(obj: Any, fallback: tuple[str, str]) -> tuple[str, str]:
    module = getattr(obj, "__module__", None)
    qualname = getattr(obj, "__qualname__", None)
    if isinstance(module, str) and isinstance(qualname, str):
        return module, qualname
    return fallback


def _script_entry(target: str) -> tuple[str, str]:
    module_name, _, attribute = target.partition(":")
    obj: Any = importlib.import_module(module_name)
    for part in attribute.split(".") if attribute else ():
        obj = getattr(obj, part)
    return _qualified(obj, (module_name, attribute))


def _exported_entries(package_name: str) -> list[tuple[str, str]]:
    package = importlib.import_module(package_name)
    entries: list[tuple[str, str]] = []
    for exported in getattr(package, "__all__", ()):
        obj = getattr(package, exported)
        module = getattr(obj, "__module__", None)
        qualname = getattr(obj, "__qualname__", None)
        if isinstance(module, str) and isinstance(qualname, str):
            entries.append((module, qualname))
    return entries


def resolve(config: dict[str, Any]) -> list[tuple[str, str]]:
    allowed: set[tuple[str, str]] = set()
    for target in config["scripts"]:
        allowed.add(_script_entry(target))
    if config["name"]:
        dist = importlib.metadata.distribution(config["name"])
        for package_name in top_level_packages(dist):
            allowed.update(_exported_entries(package_name))
    return sorted(allowed)


def main() -> None:
    with open(sys.argv[1], encoding="utf-8") as handle:
        config: dict[str, Any] = json.load(handle)
    sys.path.insert(0, os.getcwd())
    try:
        entries = resolve(config)
    except importlib.metadata.PackageNotFoundError:
        raise  # not an import failure: the environment lacks the project, a harness problem
    except Exception:  # noqa: BLE001 - process boundary: an import failure is reported by exit code
        traceback.print_exc()
        sys.exit(IMPORT_FAILURE_EXIT)
    print(json.dumps({"allowed": [list(entry) for entry in entries]}))


if __name__ == "__main__":
    main()
