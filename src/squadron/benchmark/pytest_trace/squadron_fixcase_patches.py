"""Patch interception for the fix-case trace plugin (slice 422 D7).

While a test's setup or call phase runs, wraps ``unittest.mock``'s ``_patch.__enter__`` and
``_patch_dict.__enter__`` (every ``patch``, ``patch.object``, ``patch.multiple`` and
``patch.dict`` form, as a context manager, decorator or ``start()``, which calls
``__enter__``) and ``pytest.MonkeyPatch``'s ``setattr``, ``delattr``, ``setitem`` and
``delitem``. For each patch it records ``(api, owner_kind, owner_module, target)``, where the
owner is the object being modified, not the object swapped in: ``patch("pkg.mod.run")`` modifies
``pkg.mod`` even though ``run`` came from ``subprocess``.

Owner kinds: ``project_module``, ``project_class``, ``project_instance``, ``foreign`` and
``unresolved``. A mapping is owned by the project module whose globals hold that very object
(a project dict reached through a class attribute is not found and reads as foreign).

Runs inside the project's own environment, so it imports only the standard library, pytest
and its sibling plugin module.
"""

from __future__ import annotations

import functools
import importlib
import inspect
import logging
import sys
import types
import unittest.mock as mock
from collections.abc import Callable, MutableMapping
from typing import Any, cast

import pytest
import squadron_fixcase_closure

_logger = logging.getLogger(__name__)

OWNER_PROJECT_MODULE = "project_module"
OWNER_PROJECT_CLASS = "project_class"
OWNER_PROJECT_INSTANCE = "project_instance"
OWNER_FOREIGN = "foreign"
OWNER_UNRESOLVED = "unresolved"

Patch = tuple[str, str, str, str]
_Method = Callable[..., Any]


class PatchInterceptor:
    def __init__(self, closures: squadron_fixcase_closure.ClosureBuilder) -> None:
        self._closures = closures
        self._recorded: dict[str, set[Patch]] = {}
        self._node_id: str | None = None
        self._originals: list[tuple[Any, str, _Method]] = []

    # ------------------------------------------------------------------ lifecycle

    def install(self) -> None:
        """Wrap every interception point; ``uninstall`` puts the originals back."""
        for owner, name, api, wrapper in (
            (mock._patch, "__enter__", "mock.patch", self._wrap_mock_enter),  # pyright: ignore[reportPrivateUsage]
            (mock._patch_dict, "__enter__", "mock.patch.dict", self._wrap_mock_enter),  # pyright: ignore[reportPrivateUsage]
            (pytest.MonkeyPatch, "setattr", "monkeypatch.setattr", self._wrap_monkeypatch),
            (pytest.MonkeyPatch, "delattr", "monkeypatch.delattr", self._wrap_monkeypatch),
            (pytest.MonkeyPatch, "setitem", "monkeypatch.setitem", self._wrap_monkeypatch),
            (pytest.MonkeyPatch, "delitem", "monkeypatch.delitem", self._wrap_monkeypatch),
        ):
            original: _Method = getattr(owner, name)
            self._originals.append((owner, name, original))
            setattr(owner, name, wrapper(api, original))

    def uninstall(self) -> None:
        for owner, name, original in reversed(self._originals):
            setattr(owner, name, original)
        self._originals = []

    def activate(self, node_id: str) -> None:
        self._node_id = node_id
        self._recorded.setdefault(node_id, set())

    def deactivate(self) -> None:
        self._node_id = None

    def patches(self, node_id: str) -> list[list[str]]:
        return [list(patch) for patch in sorted(self._recorded.get(node_id, ()))]

    def _record(self, api: str, owner_kind: str, owner_module: str, target: str) -> None:
        if self._node_id is not None:
            self._recorded[self._node_id].add((api, owner_kind, owner_module, target))

    # ------------------------------------------------------------------- wrappers

    def _wrap_mock_enter(self, api: str, original: _Method) -> _Method:
        @functools.wraps(original)
        def enter(patcher: Any, *args: Any, **kwargs: Any) -> Any:
            try:
                result = original(patcher, *args, **kwargs)
            except (ImportError, AttributeError):
                # The target did not resolve: record that, then let the failure through.
                self._record(api, OWNER_UNRESOLVED, "", _unresolved_target(patcher))
                _logger.exception("%s target did not resolve", api)
                raise
            if isinstance(patcher, mock._patch_dict):  # pyright: ignore[reportPrivateUsage]
                self._record_owner(api, patcher.in_dict, "")
            else:
                self._record_owner(api, patcher.target, patcher.attribute)
            return result

        return enter

    def _wrap_monkeypatch(self, api: str, original: _Method) -> _Method:
        signature = inspect.signature(original)
        verb = api.rsplit(".", 1)[1]

        @functools.wraps(original)
        def patched(monkeypatch: Any, *args: Any, **kwargs: Any) -> Any:
            bound = signature.bind(monkeypatch, *args, **kwargs)
            bound.apply_defaults()
            self._record_monkeypatch(api, verb, bound.arguments, signature)
            return original(monkeypatch, *args, **kwargs)

        return patched

    # ------------------------------------------------------------------ recording

    def _record_monkeypatch(
        self, api: str, verb: str, arguments: dict[str, Any], signature: inspect.Signature
    ) -> None:
        target = arguments["target" if verb in ("setattr", "delattr") else "dic"]
        if verb in ("setitem", "delitem"):
            self._record_owner(api, target, f"[{arguments['name']!r}]")
            return
        # The dotted-path forms (target is a string) leave this parameter at its default.
        deciding = "value" if verb == "setattr" else "name"
        if isinstance(target, str) and arguments[deciding] is signature.parameters[deciding].default:
            self._record_dotted(api, target)
        else:
            self._record_owner(api, target, str(arguments["name"]))

    def _record_dotted(self, api: str, dotted: str) -> None:
        """``monkeypatch.setattr("pkg.mod.attr", ...)``: the owner is ``pkg.mod``."""
        owner_path, _, attribute = dotted.rpartition(".")
        try:
            owner = _resolve_dotted(owner_path)
        except (ImportError, AttributeError, ValueError):
            # Swallowing is correct: the target is recorded as unresolved (which the
            # verdict rejects), and the wrapper then calls the original setattr/delattr,
            # which raises the real error for the test itself.
            self._record(api, OWNER_UNRESOLVED, "", dotted)
            return
        self._record_owner(api, owner, attribute)

    def _record_owner(self, api: str, owner: Any, attribute: str) -> None:
        kind, module, target = self._describe(owner, attribute)
        self._record(api, kind, module, target)

    def _describe(self, owner: Any, attribute: str) -> tuple[str, str, str]:
        """``(owner kind, owner module, target)`` for a modification of ``owner.attribute``."""
        if isinstance(owner, types.ModuleType):
            project = self._closures.is_project_file(getattr(owner, "__file__", None))
            kind = OWNER_PROJECT_MODULE if project else OWNER_FOREIGN
            return kind, owner.__name__, f"{owner.__name__}.{attribute}"
        if isinstance(owner, type):
            return self._class_owner(owner, OWNER_PROJECT_CLASS, attribute)
        if isinstance(owner, MutableMapping):
            owner = cast("MutableMapping[Any, Any]", owner)
            return self._mapping_owner(owner, attribute)
        instance_class = cast("type[Any]", type(owner))
        return self._class_owner(instance_class, OWNER_PROJECT_INSTANCE, attribute)

    def _class_owner(self, cls: type, project_kind: str, attribute: str) -> tuple[str, str, str]:
        try:
            source_file = inspect.getsourcefile(cls)
        except TypeError:
            source_file = None
        kind = project_kind if self._closures.is_project_file(source_file) else OWNER_FOREIGN
        return kind, cls.__module__, f"{cls.__module__}.{cls.__qualname__}.{attribute}"

    def _mapping_owner(self, mapping: MutableMapping[Any, Any], attribute: str) -> tuple[str, str, str]:
        for module in list(sys.modules.values()):
            if not self._closures.is_project_file(getattr(module, "__file__", None)):
                continue
            for name, value in list(vars(module).items()):
                if value is mapping:
                    return OWNER_PROJECT_MODULE, module.__name__, f"{module.__name__}.{name}{attribute}"
        return OWNER_FOREIGN, "", f"<mapping>{attribute}"


def _resolve_dotted(path: str) -> Any:
    """The object at ``a.b.c``: the longest importable module prefix, then attributes."""
    if not path:
        raise ValueError("empty target path")
    parts = path.split(".")
    for split in range(len(parts), 0, -1):
        try:
            current: Any = importlib.import_module(".".join(parts[:split]))
        except ImportError:
            # Swallowing is correct: this prefix is not a module, so try a shorter one;
            # the ImportError after the loop reports a path with no importable prefix.
            continue
        for attribute in parts[split:]:
            current = getattr(current, attribute)
        return current
    raise ImportError(f"cannot import any prefix of {path}")


def _unresolved_target(patcher: Any) -> str:
    """Best-effort name for a patch whose target did not resolve.

    ``mock`` keeps the target string inside ``getter``: as a ``partial`` argument in recent
    Pythons, as a closure cell in older ones.
    """
    attribute = getattr(patcher, "attribute", "") or ""
    getter = getattr(patcher, "getter", None)
    candidates: list[Any] = list(getattr(getter, "args", ()))
    candidates += [cell.cell_contents for cell in getattr(getter, "__closure__", None) or ()]
    for candidate in candidates:
        if isinstance(candidate, str):
            return f"{candidate}.{attribute}" if attribute else candidate
    return attribute or "<unknown>"
