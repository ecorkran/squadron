"""classify and fold_records on small synthetic records (real-pytest coverage is Task 23)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from squadron.benchmark.adapter import FailureKind, NodeOutcome
from squadron.benchmark.python_failure import REPORT_KEYS, classify, fold_records

TREE = Path("/work/tree")
PROJECT_FILE = str(TREE / "src/pkg/core.py")
TEST_FILE = str(TREE / "tests/test_core.py")
HELPER_FILE = str(TREE / "tests/test_support.py")
VENV_FILE = str(TREE / ".venv/lib/python3.12/site-packages/dep/mod.py")


def rec(phase: str = "call", outcome: str = "failed", **fields: Any) -> dict[str, Any]:
    base: dict[str, Any] = dict.fromkeys(REPORT_KEYS)
    base.update(node_id="tests/test_core.py::test_x", phase=phase, outcome=outcome)
    base.update(fields)
    return base


def test_import_error_naming_project_module_is_missing_symbol() -> None:
    record = rec(exc_type="ImportError", exc_module="builtins", named_module_file=PROJECT_FILE)
    assert classify(record, TREE) is FailureKind.MISSING_SYMBOL


def test_import_error_naming_third_party_is_other() -> None:
    record = rec(
        exc_type="ModuleNotFoundError",
        exc_module="builtins",
        named_module_file=VENV_FILE,
        frame_file="<frozen importlib._bootstrap>",
    )
    assert classify(record, TREE) is FailureKind.OTHER_EXCEPTION


def test_attribute_error_on_project_module_is_missing_symbol() -> None:
    record = rec(exc_type="AttributeError", exc_module="builtins", named_module_file=PROJECT_FILE)
    assert classify(record, TREE) is FailureKind.MISSING_SYMBOL


def test_attribute_error_in_test_helper_is_other() -> None:
    record = rec(exc_type="AttributeError", exc_module="builtins", frame_file=HELPER_FILE)
    assert classify(record, TREE) is FailureKind.OTHER_EXCEPTION


@pytest.mark.parametrize(
    ("exc_type", "exc_module"),
    [("AssertionError", "builtins"), ("Failed", "_pytest.outcomes")],
)
def test_assertions_and_pytest_fail(exc_type: str, exc_module: str) -> None:
    record = rec(exc_type=exc_type, exc_module=exc_module, frame_file=TEST_FILE)
    assert classify(record, TREE) is FailureKind.ASSERTION_FAILURE


def test_project_frame_is_project_exception_and_venv_frame_is_other() -> None:
    crash = rec(exc_type="ZeroDivisionError", exc_module="builtins", frame_file=PROJECT_FILE)
    assert classify(crash, TREE) is FailureKind.PROJECT_EXCEPTION
    dep = rec(exc_type="ValueError", exc_module="builtins", frame_file=VENV_FILE)
    assert classify(dep, TREE) is FailureKind.OTHER_EXCEPTION


def test_collection_record_beats_a_project_import_error() -> None:
    record = rec(
        phase="collect",
        exc_type="ImportError",
        exc_module="builtins",
        named_module_file=PROJECT_FILE,
    )
    assert classify(record, TREE) is FailureKind.COLLECTION_ERROR


def fold(*records: dict[str, Any]) -> Any:
    return fold_records(records, TREE)["tests/test_core.py::test_x"]


def test_failed_setup_beats_a_call_record() -> None:
    result = fold(
        rec("setup", exc_type="ValueError", exc_module="builtins", frame_file=TEST_FILE),
        rec("call", "passed"),
    )
    assert result.outcome is NodeOutcome.ERROR
    assert result.phase == "setup"


def test_failed_call_with_failed_teardown_is_failed() -> None:
    result = fold(
        rec("call", exc_type="AssertionError", exc_module="builtins"),
        rec("teardown", exc_type="ValueError", exc_module="builtins"),
    )
    assert result.outcome is NodeOutcome.FAILED
    assert result.failure_kind is FailureKind.ASSERTION_FAILURE


def test_passed_call_with_failed_teardown_is_error() -> None:
    result = fold(rec("call", "passed"), rec("teardown", exc_type="ValueError", exc_module="x"))
    assert result.outcome is NodeOutcome.ERROR
    assert result.phase == "teardown"


def test_setup_skip_with_no_call_is_skipped() -> None:
    result = fold(rec("setup", "skipped"), rec("teardown", "passed"))
    assert result.outcome is NodeOutcome.SKIPPED
    assert result.failure_kind is None


@pytest.mark.parametrize("outcome", ["xfailed", "xpassed", "passed", "skipped"])
def test_call_outcomes_map_through(outcome: str) -> None:
    assert fold(rec("setup", "passed"), rec("call", outcome)).outcome is NodeOutcome(outcome)


def test_collect_record_becomes_error_under_the_file_node_id() -> None:
    record = rec("collect", node_id="tests/test_bad.py", exc_type="ModuleNotFoundError")
    result = fold_records([record], TREE)["tests/test_bad.py"]
    assert result.outcome is NodeOutcome.ERROR
    assert result.failure_kind is FailureKind.COLLECTION_ERROR
