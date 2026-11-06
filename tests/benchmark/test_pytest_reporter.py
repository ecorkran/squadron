"""The injected pytest reporter plugin, run for real against classify_project."""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import subprocess
import sys
import zipfile
from collections import defaultdict
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from squadron.benchmark.python_failure import (
    REPORT_KEYS,
    REPORT_PATH_ENV,
    REPORTER_MODULE,
    reporter_plugin_dir,
)
from tests.benchmark.support import git_tree

PLUGIN_FILE = reporter_plugin_dir() / f"{REPORTER_MODULE}.py"


def run_pytest(tree: Path, out: Path, *args: str) -> list[dict[str, Any]]:
    env = {
        **os.environ,
        "PYTHONPATH": str(reporter_plugin_dir()),
        REPORT_PATH_ENV: str(out),
    }
    subprocess.run(
        [sys.executable, "-m", "pytest", "-p", REPORTER_MODULE, "-p", "no:cacheprovider", *args],
        cwd=tree,
        env=env,
        capture_output=True,
        check=False,
    )
    return [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]


@pytest.fixture(scope="module")
def records(tmp_path_factory: pytest.TempPathFactory) -> list[dict[str, Any]]:
    base = tmp_path_factory.mktemp("reporter")
    tree = git_tree("classify_project", base)
    return run_pytest(tree, base / "report.jsonl", "--continue-on-collection-errors")


def by_node(records: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    nodes: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for record in records:
        nodes[record["node_id"]][record["phase"]] = record
    return nodes


def test_every_line_has_exactly_the_report_keys(records: list[dict[str, Any]]) -> None:
    assert records
    assert all(tuple(record) == REPORT_KEYS for record in records)


def test_executed_nodes_have_a_line_per_phase(records: list[dict[str, Any]]) -> None:
    nodes = by_node(records)
    classify = "tests/test_classify.py::"
    assert set(nodes[f"{classify}test_assertion"]) == {"setup", "call", "teardown"}
    assert set(nodes[f"{classify}test_passes"]) == {"setup", "call", "teardown"}
    # A skip in setup has no call phase.
    assert set(nodes[f"{classify}test_skipped"]) == {"setup", "teardown"}
    assert nodes[f"{classify}test_skipped"]["setup"]["outcome"] == "skipped"
    assert nodes[f"{classify}test_expected_failure"]["call"]["outcome"] == "xfailed"


def test_bracketed_parametrized_id_is_recorded_exactly(records: list[dict[str, Any]]) -> None:
    assert "tests/test_classify.py::test_bracketed_id[a[1]]" in by_node(records)


def test_failing_nodes_carry_exception_identity(records: list[dict[str, Any]]) -> None:
    nodes = by_node(records)
    classify = "tests/test_classify.py::"
    crash = nodes[f"{classify}test_project_crash"]["call"]
    assert (crash["exc_type"], crash["exc_module"]) == ("ZeroDivisionError", "builtins")
    assert crash["frame_file"].endswith("pkg/core.py")
    assert nodes[f"{classify}test_assertion"]["call"]["exc_type"] == "AssertionError"


def test_named_module_file_for_import_attribute_and_mock(records: list[dict[str, Any]]) -> None:
    nodes = by_node(records)
    classify = "tests/test_classify.py::"
    for name in (
        "test_missing_import",
        "test_module_attribute_error",
        "test_mock_patch_missing_target",
    ):
        named = nodes[f"{classify}{name}"]["call"]["named_module_file"]
        assert named is not None
        assert named.endswith("pkg/core.py"), name
    assert nodes[f"{classify}test_exception_in_test_code"]["call"]["named_module_file"] is None


def test_collection_failure_has_its_own_line(records: list[dict[str, Any]]) -> None:
    collect = by_node(records)["tests/test_collect_fails.py"]["collect"]
    assert collect["outcome"] == "failed"
    assert collect["exc_type"] == "ModuleNotFoundError"


def test_empty_file_exists_when_nothing_is_collected(tmp_path: Path) -> None:
    tree = git_tree("classify_project", tmp_path)
    out = tmp_path / "empty.jsonl"
    assert (
        run_pytest(tree, out, "--ignore=tests/test_collect_fails.py", "-k", "no_such_test_name") == []
    )
    assert out.exists()


def test_plugin_constants_match_the_harness() -> None:
    spec = importlib.util.spec_from_file_location("reporter_under_test", PLUGIN_FILE)
    assert spec is not None and spec.loader is not None
    module: ModuleType = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.REPORT_PATH_ENV == REPORT_PATH_ENV
    assert module.REPORT_KEYS == REPORT_KEYS


def test_plugin_imports_only_stdlib_and_pytest() -> None:
    allowed = set(sys.stdlib_module_names) | {"pytest"}
    imported: set[str] = set()
    for node in ast.walk(ast.parse(PLUGIN_FILE.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            imported |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert imported <= allowed, imported - allowed


@pytest.mark.network
def test_wheel_ships_the_plugin(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(tmp_path)],
        cwd=repo_root,
        check=True,
        capture_output=True,
    )
    [wheel] = tmp_path.glob("*.whl")
    names = zipfile.ZipFile(wheel).namelist()
    assert f"squadron/benchmark/pytest_reporter/{REPORTER_MODULE}.py" in names
