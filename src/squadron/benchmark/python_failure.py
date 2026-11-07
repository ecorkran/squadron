"""Harness side of the pytest reporter: the record contract, folding and classification.

The plugin (``pytest_reporter/squadron_benchmark_reporter.py``) cannot import this module
because it runs in the project's own environment, so it repeats ``REPORT_PATH_ENV`` and
``REPORT_KEYS``; a test asserts they agree.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from squadron.benchmark.adapter import FailureKind, NodeOutcome, NodeResult

REPORT_PATH_ENV = "SQUADRON_BENCHMARK_REPORT"
REPORT_KEYS = (
    "node_id",
    "phase",
    "outcome",
    "exc_type",
    "exc_module",
    "named_module_file",
    "frame_file",
    "frame_line",
)
REPORTER_MODULE = "squadron_benchmark_reporter"


def reporter_plugin_dir() -> Path:
    """The directory holding the reporter plugin, located from this file, never the cwd."""
    return Path(__file__).parent / "pytest_reporter"


PHASE_COLLECT = "collect"
PHASE_SETUP = "setup"
PHASE_CALL = "call"
PHASE_TEARDOWN = "teardown"
_FAILED = "failed"
_IMPORT_ERRORS = ("ImportError", "ModuleNotFoundError")
_ATTRIBUTE_ERROR = "AttributeError"
_ASSERTION_ERROR = "AssertionError"
_PYTEST_OUTCOMES_MODULE = "_pytest.outcomes"
_PYTEST_FAILED = "Failed"
_TEST_FILE_PATTERNS = ("test_*.py", "*_test.py", "conftest.py")
VENV_DIR = ".venv"

Record = Mapping[str, Any]


def venv_bin(tree: Path) -> Path:
    """The ``bin`` directory of the environment installed in ``tree``."""
    return tree / VENV_DIR / "bin"


def is_project_source(path: str | None, tree: Path) -> bool:
    """A file under ``tree``, not under ``.venv``, and not a test module or conftest."""
    if not path:
        return False
    try:
        relative = Path(path).resolve().relative_to(tree.resolve())
    except ValueError:
        return False
    if VENV_DIR in relative.parts:
        return False
    return not any(fnmatch(relative.name, pattern) for pattern in _TEST_FILE_PATTERNS)


def classify(record: Record, tree: Path) -> FailureKind:
    """Assign a ``FailureKind`` in D11's order: collection, symbol, assertion, project, other."""
    if record["phase"] == PHASE_COLLECT:
        return FailureKind.COLLECTION_ERROR
    exc_type, exc_module = record["exc_type"], record["exc_module"]
    names_project_module = is_project_source(record["named_module_file"], tree)
    if names_project_module and (
        (exc_module == "builtins" and exc_type in _IMPORT_ERRORS) or exc_type == _ATTRIBUTE_ERROR
    ):
        return FailureKind.MISSING_SYMBOL
    if exc_type == _ASSERTION_ERROR or (
        exc_module == _PYTEST_OUTCOMES_MODULE and exc_type == _PYTEST_FAILED
    ):
        return FailureKind.ASSERTION_FAILURE
    if is_project_source(record["frame_file"], tree):
        return FailureKind.PROJECT_EXCEPTION
    return FailureKind.OTHER_EXCEPTION


def _failed_result(record: Record, outcome: NodeOutcome, tree: Path) -> NodeResult:
    return NodeResult(
        node_id=record["node_id"],
        outcome=outcome,
        failure_kind=classify(record, tree),
        phase=record["phase"],
        exception_type=record["exc_type"],
    )


def _fold_node(phases: Mapping[str, Record], tree: Path) -> NodeResult:
    """One node's result from its per-phase records (setup beats call beats teardown)."""
    if PHASE_COLLECT in phases:
        return _failed_result(phases[PHASE_COLLECT], NodeOutcome.ERROR, tree)
    setup, call, teardown = (phases.get(p) for p in (PHASE_SETUP, PHASE_CALL, PHASE_TEARDOWN))
    if setup is not None and setup["outcome"] == _FAILED:
        return _failed_result(setup, NodeOutcome.ERROR, tree)
    if call is not None and call["outcome"] == _FAILED:
        return _failed_result(call, NodeOutcome.FAILED, tree)
    if teardown is not None and teardown["outcome"] == _FAILED:
        return _failed_result(teardown, NodeOutcome.ERROR, tree)
    deciding = call if call is not None else setup
    if deciding is None:
        raise ValueError(f"no setup or call record for node {next(iter(phases.values()))['node_id']}")
    return NodeResult(
        node_id=deciding["node_id"],
        outcome=NodeOutcome(deciding["outcome"]),
        phase=deciding["phase"],
        exception_type=deciding["exc_type"],
    )


def fold_records(records: Iterable[Record], tree: Path) -> dict[str, NodeResult]:
    """One ``NodeResult`` per node, folded from the reporter's per-phase records."""
    phases_by_node: dict[str, dict[str, Record]] = {}
    for record in records:
        phases_by_node.setdefault(record["node_id"], {})[record["phase"]] = record
    return {node_id: _fold_node(phases, tree) for node_id, phases in phases_by_node.items()}
