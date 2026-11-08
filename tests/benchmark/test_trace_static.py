"""Trace plugin, trace mode: static references (slice 422 D6).

Runs the harness's pytest (no venv) over ``fixfair_project`` and reads the ``references`` each
node's closure names. A reference is ``[kind, module, qualname]``; a module's qualname is empty.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests.benchmark.support import git_tree, run_trace_plugin

BASE = "tests/test_boundary_static.py::"
EXPORTED = ["function", "fixpkg.api", "exported_function"]
INTERNAL = ["function", "fixpkg.internal", "internal_function"]
WIDGET = ["class", "fixpkg.internal", "InternalWidget"]
CLI_MAIN = ["function", "fixpkg.cli", "main"]


@pytest.fixture(scope="module")
def nodes(tmp_path_factory: pytest.TempPathFactory) -> dict[str, dict[str, Any]]:
    root = tmp_path_factory.mktemp("trace_static")
    run = run_trace_plugin(git_tree("fixfair_project", root), root / "out", "trace", ["tests"])
    assert run.returncode == 0, run.stderr
    assert run.output["has_co_qualname"] is True
    return run.output["nodes"]


def references(nodes: dict[str, dict[str, Any]], name: str) -> list[list[str]]:
    return nodes[f"{BASE}{name}"]["references"]


def test_a_reference_to_an_exported_function_is_reported_where_it_is_defined(
    nodes: dict[str, dict[str, Any]],
) -> None:
    assert references(nodes, "test_ref_exported_function") == [EXPORTED]


def test_a_reference_to_an_internal_function(nodes: dict[str, dict[str, Any]]) -> None:
    assert references(nodes, "test_ref_internal_function") == [INTERNAL]


def test_a_reference_to_a_non_exported_class(nodes: dict[str, dict[str, Any]]) -> None:
    assert references(nodes, "test_ref_non_exported_class") == [WIDGET]


def test_a_reference_to_a_project_module_object(nodes: dict[str, dict[str, Any]]) -> None:
    assert references(nodes, "test_ref_project_module_object") == [["module", "fixpkg", ""]]


def test_a_fixture_that_reaches_an_internal_function(nodes: dict[str, dict[str, Any]]) -> None:
    assert references(nodes, "test_fixture_reaches_internal") == [INTERNAL]


def test_a_test_side_helper_that_reaches_an_internal_function(
    nodes: dict[str, dict[str, Any]],
) -> None:
    assert references(nodes, "test_helper_reaches_internal") == [INTERNAL]


def test_driving_the_cli_entry_point_references_only_the_script_target(
    nodes: dict[str, dict[str, Any]],
) -> None:
    assert references(nodes, "test_drives_the_cli_entry_point") == [CLI_MAIN]


def test_nested_code_objects_are_followed(nodes: dict[str, dict[str, Any]]) -> None:
    assert references(nodes, "test_lambda_names_a_project_function") == [EXPORTED]
    assert references(nodes, "test_comprehension_names_a_project_function") == [INTERNAL]


def test_a_test_naming_nothing_from_the_project_has_no_references(
    nodes: dict[str, dict[str, Any]],
) -> None:
    assert references(nodes, "test_names_nothing_from_the_project") == []


def test_trace_mode_reports_no_patches_until_the_patch_interception_task(
    nodes: dict[str, dict[str, Any]],
) -> None:
    record = nodes[f"{BASE}test_ref_exported_function"]
    assert record["patches"] == []


def test_existing_tests_keep_their_references(nodes: dict[str, dict[str, Any]]) -> None:
    # The base fixture's own tests name the exported function only.
    assert nodes["tests/test_reach.py::test_direct_body"]["references"] == [EXPORTED]


def test_the_named_node_ids_are_the_only_ones_traced(tmp_path: Path) -> None:
    tree = git_tree("fixfair_project", tmp_path)
    run = run_trace_plugin(tree, tmp_path / "out", "trace", [f"{BASE}test_ref_internal_function"])
    assert list(run.output["nodes"]) == [f"{BASE}test_ref_internal_function"]
