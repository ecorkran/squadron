"""Python grading: tool-config restoration, dependency changes and test edits, and the adapter
that gathers them with injection and suppression counting (slice 425 D3-D6).

The producer's tree is graded under the start commit's tool config, so pytest, ruff and
pyright run as they did when the case was qualified. What the producer may change is the
packaging side (``[project]``, ``[dependency-groups]``, ``[build-system]`` and the tables in
``PACKAGING_TOOL_TABLES``), because that decides which dependencies get installed.
"""

from __future__ import annotations

import logging
import tomllib
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import tomli_w

from squadron.benchmark.grading_adapter import (
    InjectionResult,
    ProducerConfigError,
    RestorationResult,
)
from squadron.benchmark.python_fairness import PythonFixCaseAdapter
from squadron.benchmark.python_injection import inject_hidden
from squadron.benchmark.python_suppressions import count_suppressions
from squadron.benchmark.tree_reader import TreeReader, TreeReadError
from squadron.config.manager import PROJECT_CONFIG_FILE
from squadron.metrology.benchmark_models import BenchmarkCase
from squadron.metrology.grade_models import SuppressionCounts
from squadron.metrology.snapshot_models import SourceLanguage

_logger = logging.getLogger(__name__)

PYPROJECT = "pyproject.toml"
LOCKFILE = "uv.lock"
TOOL_KEY = "tool"
TOOL_NAME_PREFIX = "tool."
#: ``[tool.*]`` tables that decide dependencies and packaging, so they follow the producer.
PACKAGING_TOOL_TABLES = (
    "uv",
    "hatch",
    "setuptools",
    "poetry",
    "pdm",
    "flit",
    "maturin",
    "scikit-build",
)
#: Standalone tool config files, restored to their start content or deleted.
TOOL_CONFIG_FILES = (
    "ruff.toml",
    ".ruff.toml",
    "pyrightconfig.json",
    "mypy.ini",
    "pytest.ini",
    ".coveragerc",
    # pytest reads [tool:pytest] from setup.cfg and [pytest] from tox.ini.
    "setup.cfg",
    "tox.ini",
    # The snapshot reads its exclusions, limits and timeout from it (slice 400).
    PROJECT_CONFIG_FILE,
)


def _parse(text: str, path: str, *, producer: bool) -> dict[str, Any]:
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        _logger.error("%s does not parse as TOML: %s", path, exc)
        if producer:
            raise ProducerConfigError(path, f"does not parse as TOML: {exc}") from exc
        raise TreeReadError(f"parse {path} at the start commit", str(exc)) from exc


def _producer_pyproject(tree: Path) -> dict[str, Any]:
    path = tree / PYPROJECT
    if not path.exists():
        return {}
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        _logger.error("%s is not valid UTF-8: %s", PYPROJECT, exc)
        raise ProducerConfigError(PYPROJECT, f"is not valid UTF-8: {exc}") from exc
    return _parse(text, PYPROJECT, producer=True)


def _start_pyproject(start: TreeReader, paths: frozenset[str]) -> dict[str, Any]:
    if PYPROJECT not in paths:
        return {}
    return _parse(start.read(PYPROJECT).decode("utf-8"), PYPROJECT, producer=False)


def _tool_tables(data: dict[str, Any]) -> dict[str, Any]:
    tools: dict[str, Any] = data.get(TOOL_KEY, {})
    return tools


def _restorable(names: set[str]) -> list[str]:
    return sorted(name for name in names if name not in PACKAGING_TOOL_TABLES)


def restore_tool_config(tree: Path, start: TreeReader) -> RestorationResult:
    """Put the start commit's tool config back by section; report what differed (D4).

    Every non-packaging ``[tool.*]`` table of ``pyproject.toml`` comes from the start commit
    (a table the start lacked is removed), and each standalone file in ``TOOL_CONFIG_FILES``
    is restored or deleted. ``config_edits`` names each table (``tool.ruff``) or file
    (``pyrightconfig.json``) whose producer content differed. A ``pyproject.toml`` the
    producer left unparseable raises ``ProducerConfigError``.
    """
    paths = frozenset(start.list_paths())
    edits = [*_restore_pyproject_tables(tree, start, paths), *_restore_files(tree, start, paths)]
    return RestorationResult(config_edits=tuple(sorted(edits)))


def _restore_pyproject_tables(tree: Path, start: TreeReader, paths: frozenset[str]) -> list[str]:
    if not (tree / PYPROJECT).exists():
        # The producer deleted it. Writing the start's tool tables into a new file would make
        # a partial pyproject without [project]; leave it deleted, deps_changed sees the
        # loss and the reinstall records the unresolvable environment.
        return []
    producer = _producer_pyproject(tree)
    start_tools = _tool_tables(_start_pyproject(start, paths))
    producer_tools = _tool_tables(producer)
    differing = [
        name
        for name in _restorable(set(producer_tools) | set(start_tools))
        if producer_tools.get(name) != start_tools.get(name)
    ]
    if not differing:
        return []
    merged = dict(producer_tools)
    for name in differing:
        if name in start_tools:
            merged[name] = start_tools[name]
        else:
            del merged[name]
    if merged:
        producer[TOOL_KEY] = merged
    else:
        producer.pop(TOOL_KEY, None)
    (tree / PYPROJECT).write_text(tomli_w.dumps(producer), encoding="utf-8")
    return [f"{TOOL_NAME_PREFIX}{name}" for name in differing]


def _normalized(content: bytes) -> bytes:
    return content.replace(b"\r\n", b"\n")


def _restore_files(tree: Path, start: TreeReader, paths: frozenset[str]) -> list[str]:
    edits: list[str] = []
    for name in TOOL_CONFIG_FILES:
        producer_file = tree / name
        at_start = start.read(name) if name in paths else None
        produced = producer_file.read_bytes() if producer_file.exists() else None
        same = (at_start is None and produced is None) or (
            at_start is not None
            and produced is not None
            and _normalized(at_start) == _normalized(produced)
        )
        if same:
            continue
        edits.append(name)
        if at_start is None:
            producer_file.unlink()
        else:
            producer_file.write_bytes(at_start)
    return edits


def _without_restorable_tools(data: dict[str, Any]) -> dict[str, Any]:
    kept = {key: value for key, value in data.items() if key != TOOL_KEY}
    tools = {name: table for name, table in _tool_tables(data).items() if name in PACKAGING_TOOL_TABLES}
    if tools:
        kept[TOOL_KEY] = tools
    return kept


def _lockfile(
    tree: Path, start: TreeReader, paths: frozenset[str]
) -> tuple[bytes | None, bytes | None]:
    producer = (tree / LOCKFILE).read_bytes() if (tree / LOCKFILE).exists() else None
    at_start = start.read(LOCKFILE) if LOCKFILE in paths else None
    return producer, at_start


def deps_changed(tree: Path, start: TreeReader) -> bool:
    """Whether the producer changed dependencies or the lock (D5).

    True when ``uv.lock`` differs from the start's, or when ``pyproject.toml`` with the
    restorable tool tables removed differs in parsed content (comments and formatting do not
    count). A ``pyproject.toml`` the producer left unparseable raises ``ProducerConfigError``.
    """
    paths = frozenset(start.list_paths())
    producer_lock, start_lock = _lockfile(tree, start, paths)
    if producer_lock is not None and start_lock is not None:
        if _normalized(producer_lock) != _normalized(start_lock):
            return True
    elif producer_lock != start_lock:
        return True
    producer = _without_restorable_tools(_producer_pyproject(tree))
    return producer != _without_restorable_tools(_start_pyproject(start, paths))


def _start_pyproject_text(start: TreeReader, paths: frozenset[str]) -> str | None:
    return start.read(PYPROJECT).decode("utf-8") if PYPROJECT in paths else None


def test_side_edits(tree: Path, start: TreeReader) -> tuple[str, ...]:
    """Existing test-side files the producer modified or deleted, sorted (D6).

    Test-side is 422's ``is_test_side``, judged at the start tree (its ``testpaths``), and
    limited to test source files: ``GitTreeReader`` returns decoded text, so a binary test
    data file cannot be compared. Files the producer added are not in the start tree and so
    never appear here.
    """
    paths = frozenset(start.list_paths())
    pyproject_text = _start_pyproject_text(start, paths)
    classifier = PythonFixCaseAdapter()
    edited: list[str] = []
    for path in sorted(paths):
        if not (classifier.is_test_source(path) and classifier.is_test_side(pyproject_text, path)):
            continue
        produced = tree / path
        if not produced.exists() or _normalized(produced.read_bytes()) != _normalized(start.read(path)):
            edited.append(path)
    return tuple(edited)


def restore_test_files(tree: Path, start: TreeReader, paths: Sequence[str]) -> None:
    """Write the start content of *paths* back, recreating deleted files (D6, D1)."""
    for path in paths:
        target = tree / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(start.read(path))


class PythonGradingAdapter:
    """The Python ``GradingAdapter``: a thin composition of this slice's grading functions."""

    language = SourceLanguage.PYTHON

    def restore_tool_config(self, tree: Path, start: TreeReader) -> RestorationResult:
        return restore_tool_config(tree, start)

    def deps_changed(self, tree: Path, start: TreeReader) -> bool:
        return deps_changed(tree, start)

    def test_side_edits(self, tree: Path, start: TreeReader) -> tuple[str, ...]:
        return test_side_edits(tree, start)

    def restore_test_files(self, tree: Path, start: TreeReader, paths: Sequence[str]) -> None:
        restore_test_files(tree, start, paths)

    def inject_hidden(
        self, tree: Path, case: BenchmarkCase, start: TreeReader, reference: TreeReader
    ) -> InjectionResult:
        return inject_hidden(tree, case, start, reference)

    def count_suppressions(self, diff: bytes) -> SuppressionCounts:
        return count_suppressions(diff)
