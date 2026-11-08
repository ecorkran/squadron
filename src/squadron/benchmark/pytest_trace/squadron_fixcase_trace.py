"""pytest plugin for fix-case qualification (slice 422 D3, D6, D7).

Injected into a sandbox's pytest with ``-p squadron_fixcase_trace`` and ``PYTHONPATH``, like
421's reporter. It runs inside the project's own environment, so it imports only the
standard library, ``pytest`` and its sibling module ``squadron_fixcase_closure``.

One environment variable, ``SQUADRON_FIXCASE_TRACE_CONFIG``, names a JSON file::

    {"mode": "collect" | "trace", "tree": <path>, "test_side_files": [<relative>, ...],
     "output": <path>}

The ``output`` file is created (truncated) in ``pytest_configure``, so a file that exists
proves the plugin loaded; the result JSON is written when the session reaches its end.
"""

from __future__ import annotations

import ast
import inspect
import json
import os
from pathlib import Path
from typing import Any

import pytest
import squadron_fixcase_closure

CONFIG_PATH_ENV = "SQUADRON_FIXCASE_TRACE_CONFIG"
MODE_COLLECT = "collect"
MODE_TRACE = "trace"

_config: dict[str, Any] | None = None
_closures: squadron_fixcase_closure.ClosureBuilder | None = None


def pytest_configure(config: pytest.Config) -> None:
    global _config, _closures
    path = os.environ.get(CONFIG_PATH_ENV)
    if not path:
        raise pytest.UsageError(f"{CONFIG_PATH_ENV} is not set")
    loaded: dict[str, Any] = json.loads(Path(path).read_text(encoding="utf-8"))
    if loaded["mode"] not in (MODE_COLLECT, MODE_TRACE):
        raise pytest.UsageError(f"unknown trace mode {loaded['mode']!r}")
    _config = loaded
    _closures = squadron_fixcase_closure.ClosureBuilder(Path(loaded["tree"]), loaded["test_side_files"])
    with open(loaded["output"], "w", encoding="utf-8"):
        pass  # truncate: the file existing proves this plugin loaded


def _write_output(result: dict[str, Any]) -> None:
    if _config is None:
        raise RuntimeError("squadron_fixcase_trace wrote before pytest_configure ran")
    Path(_config["output"]).write_text(json.dumps(result), encoding="utf-8")


CONFTEST_NAME = "conftest.py"
_collection_errors: list[dict[str, str]] = []


def _active_fixtures(item: pytest.Function) -> list[Any]:
    """The fixture definitions pytest resolved for ``item``: the nearest definition of each name."""
    definitions = item._fixtureinfo.name2fixturedefs  # pyright: ignore[reportPrivateUsage]
    return [chain[-1] for chain in definitions.values() if chain]


def _conftest_reference(fixturedef: Any) -> list[str] | None:
    """``[conftest path, fixture name]`` when the fixture is defined in a test-side conftest."""
    if _closures is None:
        raise RuntimeError("squadron_fixcase_trace asked about fixtures before pytest_configure ran")
    func = inspect.unwrap(fixturedef.func)
    try:
        source_file = inspect.getsourcefile(func)
    except TypeError:
        return None
    relative = _closures.relative_file(source_file)
    if relative is None or Path(relative).name != CONFTEST_NAME:
        return None
    return [relative, str(fixturedef.argname)]


def _digest(item: pytest.Function) -> str:
    if _closures is None:
        raise RuntimeError("squadron_fixcase_trace digested before pytest_configure ran")
    # item.obj is the function, or the bound method for a test in a class.
    return _closures.digest(item.obj, [definition.func for definition in _active_fixtures(item)])


def _item_record(item: pytest.Item) -> dict[str, Any]:
    if not isinstance(item, pytest.Function):
        raise RuntimeError(f"cannot digest {item.nodeid}: {type(item).__name__} is not a function item")
    reached = [_conftest_reference(definition) for definition in _active_fixtures(item)]
    return {
        "node_id": item.nodeid,
        "digest": _digest(item),
        "fixtures": sorted(reference for reference in reached if reference is not None),
    }


def _fixture_name(node: ast.stmt) -> str | None:
    """The fixture name a top-level function defines (``name=`` overrides), else ``None``."""
    if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
        return None
    for decorator in node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        called = target.attr if isinstance(target, ast.Attribute) else getattr(target, "id", None)
        if called != "fixture":
            continue
        if isinstance(decorator, ast.Call):
            for keyword in decorator.keywords:
                if keyword.arg == "name" and isinstance(keyword.value, ast.Constant):
                    return str(keyword.value.value)
        return node.name
    return None


def _defined_conftest_fixtures(config: pytest.Config) -> list[list[str]]:
    """Every fixture defined in a loaded test-side conftest, whether or not a test reaches it.

    Read from the conftest sources rather than from pytest's fixture manager, whose
    internals differ between pytest releases.
    """
    if _closures is None:
        raise RuntimeError("squadron_fixcase_trace asked about fixtures before pytest_configure ran")
    found: set[tuple[str, str]] = set()
    for plugin in config.pluginmanager.get_plugins():
        filename = getattr(plugin, "__file__", None)
        relative = _closures.relative_file(filename)
        if filename is None or relative is None or Path(relative).name != CONFTEST_NAME:
            continue
        for node in ast.parse(Path(filename).read_text(encoding="utf-8")).body:
            name = _fixture_name(node)
            if name is not None:
                found.add((relative, name))
    return [list(pair) for pair in sorted(found)]


def pytest_collectreport(report: pytest.CollectReport) -> None:
    if report.failed:
        _collection_errors.append({"file": report.nodeid, "message": str(report.longrepr)})


def pytest_sessionfinish(session: pytest.Session) -> None:
    if _config is None or _config["mode"] != MODE_COLLECT:
        return
    _write_output(
        {
            "items": [_item_record(item) for item in session.items],
            "conftest_fixtures": _defined_conftest_fixtures(session.config),
            "collection_errors": _collection_errors,
        }
    )
