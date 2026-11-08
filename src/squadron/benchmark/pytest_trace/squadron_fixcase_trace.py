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


def _fixture_functions(item: pytest.Function) -> list[Any]:
    """The fixture functions pytest resolved for ``item``: the nearest definition of each."""
    definitions = item._fixtureinfo.name2fixturedefs  # pyright: ignore[reportPrivateUsage]
    return [chain[-1].func for chain in definitions.values() if chain]


def _digest(item: pytest.Item) -> str:
    if _closures is None:
        raise RuntimeError("squadron_fixcase_trace digested before pytest_configure ran")
    if isinstance(item, pytest.Function):
        # item.obj is the function, or the bound method for a test in a class.
        return _closures.digest(item.obj, _fixture_functions(item))
    raise RuntimeError(f"cannot digest {item.nodeid}: {type(item).__name__} is not a function item")


def _collect_result(items: list[pytest.Item]) -> dict[str, Any]:
    return {
        "items": [{"node_id": item.nodeid, "digest": _digest(item), "fixtures": []} for item in items],
        "conftest_fixtures": [],
        "collection_errors": [],
    }


def pytest_collection_finish(session: pytest.Session) -> None:
    if _config is not None and _config["mode"] == MODE_COLLECT:
        _write_output(_collect_result(session.items))
