"""Trace plugin, trace mode: dynamic crossings (slice 422 D6).

Real pytest runs (no venv) over ``fixfair_project``. A crossing is
``[module, co_qualname, kind]`` for a call from test-side code into project source.
"""

from __future__ import annotations

import sys
from typing import Any

import pytest

from tests.benchmark.support import git_tree, run_trace_plugin

PREFIX = "tests/test_boundary_crossings.py::"
EXPORTED = ["fixpkg.api", "exported_function", "function"]
INTERNAL = ["fixpkg.internal", "internal_function", "function"]
CONSTRUCTOR = ["fixpkg.internal", "InternalWidget.__init__", "constructor"]
METHOD = ["fixpkg.internal", "InternalWidget.run", "method"]


@pytest.fixture(scope="module")
def run_output(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("trace_crossings")
    run = run_trace_plugin(
        git_tree("fixfair_project", root), root / "out", "trace", ["tests/test_boundary_crossings.py"]
    )
    assert run.returncode == 0, run.stderr
    return run.output


def crossings(run_output: dict[str, Any], name: str) -> list[list[str]]:
    return run_output["nodes"][f"{PREFIX}{name}"]["crossings"]


def test_the_plugin_reports_whether_the_interpreter_has_co_qualname(run_output: dict[str, Any]) -> None:
    assert run_output["has_co_qualname"] is (sys.version_info >= (3, 11))


def test_a_call_to_an_exported_function_is_one_function_crossing(run_output: dict[str, Any]) -> None:
    assert crossings(run_output, "test_cross_exported_function") == [EXPORTED]


def test_a_call_to_an_internal_function_is_recorded(run_output: dict[str, Any]) -> None:
    assert crossings(run_output, "test_cross_internal_function") == [INTERNAL]


def test_constructing_a_class_and_calling_a_method_are_distinct_crossings(
    run_output: dict[str, Any],
) -> None:
    assert crossings(run_output, "test_cross_constructor_and_method") == [CONSTRUCTOR, METHOD]


def test_a_callback_run_by_a_dependency_is_not_a_crossing(run_output: dict[str, Any]) -> None:
    assert crossings(run_output, "test_cross_callback_run_by_exitstack") == []


def test_fixture_setup_is_part_of_what_the_test_reaches(run_output: dict[str, Any]) -> None:
    assert crossings(run_output, "test_cross_through_a_fixture_and_a_method") == [CONSTRUCTOR, METHOD]


def test_a_function_nested_in_a_test_is_a_function_not_a_method(run_output: dict[str, Any]) -> None:
    assert crossings(run_output, "test_cross_nested_function_is_a_function") == [EXPORTED]


def test_two_tests_in_one_run_do_not_leak_crossings_into_each_other(
    run_output: dict[str, Any],
) -> None:
    assert crossings(run_output, "test_cross_second_independent_test") == [EXPORTED]
    assert crossings(run_output, "test_cross_exported_function") == [EXPORTED]


def test_a_test_that_installs_its_own_profiler_does_not_break_the_run(
    run_output: dict[str, Any],
) -> None:
    # The run exited 0 (asserted by the fixture); recording continues for later tests.
    assert crossings(run_output, "test_cross_after_a_test_that_left_a_profiler") == [EXPORTED]
    # Known gap: a test that replaces the profiler hides its own later calls from it.
    assert crossings(run_output, "test_cross_restores_a_profiler_the_test_replaced") == []
    assert crossings(run_output, "test_cross_leaves_its_own_profiler_installed") == []
