"""Closure digests for the fix-case trace plugin (slice 422 D3).

A test's closure digest is a sha256 over its own source (decorators included) and the
source of every test-side definition it reaches: the fixtures pytest resolved for it, plus
the module-level functions, classes and constants named in the code objects (and
decorators) of the test and of each definition reached, recursively. "Test-side" is
membership in the configured file set; anything else (project source, the standard
library, pytest itself) is outside the closure.

Runs inside the project's own environment, so it imports only the standard library.
"""

from __future__ import annotations

import ast
import dis
import hashlib
import inspect
import textwrap
import types
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

VENV_DIR = ".venv"
_MISSING = object()
_DEFINITION_TYPES = (types.FunctionType, type)


class ClosureBuilder:
    """Collects the test-side sources one test reaches."""

    def __init__(self, tree: Path, test_side_files: Iterable[str]) -> None:
        self._tree = tree.resolve()
        self._test_side = frozenset(test_side_files)
        self._assignments: dict[str, dict[str, str]] = {}
        self._sources: dict[str, str] = {}
        self._references: set[tuple[str, str, str]] = set()

    def relative_file(self, filename: str | None) -> str | None:
        """The tree-relative posix path of ``filename`` when it is a test-side file."""
        if not filename:
            return None
        try:
            relative = Path(filename).resolve().relative_to(self._tree).as_posix()
        except ValueError:
            return None
        return relative if relative in self._test_side else None

    def is_project_file(self, filename: str | None) -> bool:
        """A file under the tree, outside ``.venv``, that is not test-side."""
        if not filename:
            return False
        try:
            relative = Path(filename).resolve().relative_to(self._tree)
        except ValueError:
            return False
        if relative.parts and relative.parts[0] == VENV_DIR:
            return False
        return relative.as_posix() not in self._test_side

    def references(self, function: Any, fixture_functions: Iterable[Any]) -> list[tuple[str, str, str]]:
        """Every project module, class or function the test side names, as ``(kind, module, qualname)``.

        Followed through the test, its fixtures and the test-side helpers they reach; a module
        reference has an empty qualname. Names are as pytest resolves them in each function's
        globals, so a re-exported function is reported where it is defined.
        """
        self._walk(function, fixture_functions)
        return sorted(self._references)

    def digest(self, function: Any, fixture_functions: Iterable[Any]) -> str:
        """The closure digest of ``function`` given the fixture functions resolved for it."""
        self._walk(function, fixture_functions)
        payload = "\n".join(f"{key}\n{self._sources[key]}" for key in sorted(self._sources))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _walk(self, function: Any, fixture_functions: Iterable[Any]) -> None:
        self._sources = {}
        self._references = set()
        for root in [function, *fixture_functions]:
            self._visit(root)

    def _visit(self, obj: Any) -> None:
        target = inspect.unwrap(obj)
        relative = self.relative_file(_source_file(target))
        if relative is None:
            return
        key = f"{relative}::{target.__qualname__}"
        if key in self._sources:
            return
        self._sources[key] = inspect.getsource(target)
        namespace: dict[str, Any] = getattr(target, "__globals__", None) or _module_namespace(target)
        names = _referenced_names(target)
        for name in sorted(names.global_names):
            self._resolve(name, namespace, names.attribute_names)

    def _resolve(self, name: str, namespace: dict[str, Any], attributes: set[str]) -> None:
        value = namespace.get(name, _MISSING)
        if value is _MISSING:
            return
        if isinstance(value, types.ModuleType):
            self._note_project_module(value)
            self._reach_module_attributes(value, attributes)
        elif isinstance(value, _DEFINITION_TYPES):
            self._note_project_definition(value)
            self._visit(value)
        else:
            self._record_constant(name, namespace)

    def _note_project_module(self, module: types.ModuleType) -> None:
        if self.is_project_file(getattr(module, "__file__", None)):
            self._references.add(("module", module.__name__, ""))

    def _note_project_definition(self, value: Any) -> None:
        if not self.is_project_file(_source_file(value)):
            return
        kind = "class" if isinstance(value, type) else "function"
        self._references.add((kind, value.__module__, value.__qualname__))

    def _reach_module_attributes(self, module: types.ModuleType, attributes: set[str]) -> None:
        """A referenced test-side module: attributes the referrer reads are reached.

        The bytecode does not say which object an attribute was read from, so any attribute
        name the referrer reads matches (an over-approximation that only widens the closure).
        """
        if self.relative_file(getattr(module, "__file__", None)) is None:
            return
        namespace = vars(module)
        for name in sorted(attributes):
            value = namespace.get(name, _MISSING)
            if isinstance(value, _DEFINITION_TYPES):
                self._note_project_definition(value)
                if getattr(value, "__module__", None) == module.__name__:
                    self._visit(value)
            elif value is not _MISSING:
                self._record_constant(name, namespace)

    def _record_constant(self, name: str, namespace: dict[str, Any]) -> None:
        filename = namespace.get("__file__")
        relative = self.relative_file(filename)
        if relative is None:
            return
        segment = self._module_assignments(str(filename)).get(name)
        if segment is not None:
            self._sources[f"{relative}::{name}"] = segment

    def _module_assignments(self, filename: str) -> dict[str, str]:
        if filename not in self._assignments:
            text = Path(filename).read_text(encoding="utf-8")
            segments: dict[str, str] = {}
            for node in ast.parse(text).body:
                for assigned in _assigned_names(node):
                    segments[assigned] = ast.get_source_segment(text, node) or ""
            self._assignments[filename] = segments
        return self._assignments[filename]


def _source_file(obj: Any) -> str | None:
    try:
        return inspect.getsourcefile(obj)
    except TypeError:
        return None


def _module_namespace(obj: Any) -> dict[str, Any]:
    module = inspect.getmodule(obj)
    return vars(module) if module is not None else {}


def _assigned_names(node: ast.stmt) -> list[str]:
    if isinstance(node, ast.Assign):
        return [target.id for target in node.targets if isinstance(target, ast.Name)]
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return [node.target.id]
    return []


_GLOBAL_LOADS = frozenset({"LOAD_GLOBAL", "LOAD_NAME"})
_ATTRIBUTE_LOADS = frozenset({"LOAD_ATTR", "LOAD_METHOD"})


@dataclass
class Names:
    """What a function or class names: global names, and attribute names read off any object."""

    global_names: set[str] = field(default_factory=set[str])
    attribute_names: set[str] = field(default_factory=set[str])

    def merge(self, other: Names) -> None:
        self.global_names |= other.global_names
        self.attribute_names |= other.attribute_names


def _code_names(code: types.CodeType) -> Names:
    """Names in a code object and in every code object nested in it (lambdas, comprehensions).

    Read from the bytecode, not ``co_names``, so a global name is not confused with an
    attribute that happens to share its spelling.
    """
    names = Names()
    for instruction in dis.get_instructions(code):
        if instruction.opname in _GLOBAL_LOADS:
            names.global_names.add(str(instruction.argval))
        elif instruction.opname in _ATTRIBUTE_LOADS:
            names.attribute_names.add(str(instruction.argval))
    for const in code.co_consts:
        if isinstance(const, types.CodeType):
            names.merge(_code_names(const))
    return names


def _decorator_names(target: Any) -> Names:
    """Names used in the decorators of a function or class: parametrize arguments live here."""
    names = Names()
    try:
        tree = ast.parse(textwrap.dedent(inspect.getsource(target)))
    except (OSError, SyntaxError, TypeError):
        return names
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            for decorator in node.decorator_list:
                for sub in ast.walk(decorator):
                    if isinstance(sub, ast.Name):
                        names.global_names.add(sub.id)
                    elif isinstance(sub, ast.Attribute):
                        names.attribute_names.add(sub.attr)
    return names


def _referenced_names(target: Any) -> Names:
    """Every name a function or class may refer to, decorators included."""
    names = _decorator_names(target)
    members = vars(target).values() if isinstance(target, type) else [target]
    for member in members:
        code = getattr(member, "__code__", None)
        if isinstance(code, types.CodeType):
            names.merge(_code_names(code))
    return names
