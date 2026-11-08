"""Trace plugin, collect mode: node ids and closure digests (slice 422 D3).

Runs the harness's own pytest over a copy of ``fixfair_project`` (no venv) with the plugin
loaded; every mutation test edits a fresh copy and compares digests with the baseline.
"""

from __future__ import annotations

import ast
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from tests.benchmark.support import git_tree, run_trace_plugin, trace_plugin_dir

FIXTURE = "fixfair_project"
DIRECT = "tests/test_reach.py::test_direct_body"
FIXTURE_USER = "tests/test_reach.py::test_uses_conftest_fixture"
HELPER_CHAIN = "tests/test_reach.py::test_uses_helper_chain"
PARAM_ONE = "tests/test_reach.py::test_parametrized[one]"
PARAM_TWO = "tests/test_reach.py::test_parametrized[two]"
BRACKETS = "tests/test_reach.py::test_bracket_id[a[b]]"
UNRELATED = "tests/test_other.py::test_unrelated"


def digests(tree: Path, work: Path) -> dict[str, str]:
    run = run_trace_plugin(tree, work, "collect")
    assert run.returncode == 0, run.stderr
    return {item["node_id"]: item["digest"] for item in run.output["items"]}


def mutated_digests(tmp_path: Path, relative: str, old: str, new: str) -> dict[str, str]:
    tree = git_tree(FIXTURE, tmp_path / "mutated")
    target = tree / relative
    text = target.read_text(encoding="utf-8")
    assert old in text, f"{old!r} not found in {relative}"
    target.write_text(text.replace(old, new, 1), encoding="utf-8")
    return digests(tree, tmp_path / "mutated_out")


@pytest.fixture(scope="module")
def baseline(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    root = tmp_path_factory.mktemp("trace_collect_baseline")
    return digests(git_tree(FIXTURE, root), root / "out")


def changed(before: dict[str, str], after: dict[str, str]) -> set[str]:
    return {node for node in before if node in after and before[node] != after[node]}


def test_baseline_lists_every_node_with_a_digest(baseline: dict[str, str]) -> None:
    assert {DIRECT, FIXTURE_USER, HELPER_CHAIN, PARAM_ONE, PARAM_TWO, BRACKETS, UNRELATED} <= set(
        baseline
    )
    assert all(len(digest) == 64 for digest in baseline.values())


def test_a_changed_test_body_changes_only_that_digest(baseline: dict[str, str], tmp_path: Path) -> None:
    after = mutated_digests(
        tmp_path,
        "tests/test_reach.py",
        "EXPECTED_DOUBLE\n\n\ndef test_uses_conftest",
        "EXPECTED_DOUBLE\n    assert True\n\n\ndef test_uses_conftest",
    )
    assert changed(baseline, after) == {DIRECT}


def test_a_changed_fixture_changes_the_tests_that_use_it(
    baseline: dict[str, str], tmp_path: Path
) -> None:
    after = mutated_digests(tmp_path, "tests/conftest.py", "return 3", "return 4")
    assert changed(baseline, after) == {FIXTURE_USER}


def test_a_changed_helper_two_levels_deep_changes_its_callers(
    baseline: dict[str, str], tmp_path: Path
) -> None:
    after = mutated_digests(tmp_path, "tests/helpers.py", "return value + 1", "return value + 2")
    assert changed(baseline, after) == {HELPER_CHAIN}


def test_changed_parametrize_ids_change_the_digest_of_the_shared_decorator(
    baseline: dict[str, str], tmp_path: Path
) -> None:
    after = mutated_digests(tmp_path, "tests/test_reach.py", 'ids=["one", "two"]', 'ids=["uno", "two"]')
    assert PARAM_ONE not in after and "tests/test_reach.py::test_parametrized[uno]" in after
    assert PARAM_TWO in changed(baseline, after)


def test_a_changed_test_side_constant_changes_the_tests_naming_it(
    baseline: dict[str, str], tmp_path: Path
) -> None:
    after = mutated_digests(
        tmp_path, "tests/test_reach.py", "EXPECTED_DOUBLE = 6", "EXPECTED_DOUBLE = 6.0"
    )
    assert changed(baseline, after) == {DIRECT, FIXTURE_USER}


def test_an_unrelated_test_changes_only_itself(baseline: dict[str, str], tmp_path: Path) -> None:
    after = mutated_digests(tmp_path, "tests/test_other.py", "1 + 1 == 2", "2 + 2 == 4")
    assert changed(baseline, after) == {UNRELATED}


def test_a_parametrized_id_with_brackets_round_trips_exactly(baseline: dict[str, str]) -> None:
    assert BRACKETS in baseline


def test_a_run_that_collects_nothing_writes_valid_json_with_empty_items(tmp_path: Path) -> None:
    tree = git_tree(FIXTURE, tmp_path)
    run = run_trace_plugin(tree, tmp_path / "out", "collect", ["-k", "no_such_test_anywhere"])
    assert run.returncode == 5
    assert run.output["items"] == []
    # Defined fixtures are reported even when no test is selected.
    assert len(run.output["conftest_fixtures"]) == 2
    assert run.output["collection_errors"] == []


def test_the_plugin_files_import_only_pytest_the_standard_library_and_each_other() -> None:
    plugin_dir = trace_plugin_dir()
    modules = {path.stem for path in plugin_dir.glob("*.py")}
    allowed = set(sys.stdlib_module_names) | {"pytest"} | modules
    for path in plugin_dir.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            imported: list[str] = []
            if isinstance(node, ast.Import):
                imported = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imported = [node.module]
            for name in imported:
                assert name.split(".")[0] in allowed, f"{path.name} imports {name}"


# --- Conftest fixtures, collection errors, packaging (Task 13) --------------------

SCALE = ["tests/conftest.py", "scale"]
WORKDIR = ["tests/conftest.py", "workdir"]


def test_each_item_lists_the_conftest_fixtures_it_reaches(tmp_path: Path) -> None:
    tree = git_tree(FIXTURE, tmp_path)
    run = run_trace_plugin(tree, tmp_path / "out", "collect")
    reached = {item["node_id"]: item["fixtures"] for item in run.output["items"]}
    assert reached[FIXTURE_USER] == [SCALE]
    assert reached["tests/test_reach.py::test_workdir_fixture"] == [WORKDIR]
    assert reached[DIRECT] == []
    assert reached[UNRELATED] == []


def test_every_defined_conftest_fixture_is_reported_by_path_and_name(tmp_path: Path) -> None:
    tree = git_tree(FIXTURE, tmp_path)
    run = run_trace_plugin(tree, tmp_path / "out", "collect")
    assert run.output["conftest_fixtures"] == [SCALE, WORKDIR]


def test_a_conftest_fixture_no_test_reaches_is_still_defined(tmp_path: Path) -> None:
    tree = git_tree(FIXTURE, tmp_path)
    conftest = tree / "tests" / "conftest.py"
    conftest.write_text(
        conftest.read_text(encoding="utf-8") + "\n\n@pytest.fixture\ndef orphan():\n    return 1\n",
        encoding="utf-8",
    )
    run = run_trace_plugin(tree, tmp_path / "out", "collect")
    assert ["tests/conftest.py", "orphan"] in run.output["conftest_fixtures"]
    assert all(["tests/conftest.py", "orphan"] not in item["fixtures"] for item in run.output["items"])


@pytest.mark.parametrize(
    ("name", "text"),
    [
        ("test_syntax.py", "def test_broken(:\n    pass\n"),
        ("test_import.py", "import module_that_does_not_exist_anywhere\n\n\ndef test_x():\n    pass\n"),
    ],
)
def test_a_test_file_that_fails_collection_is_reported_with_its_file(
    tmp_path: Path, name: str, text: str
) -> None:
    tree = git_tree(FIXTURE, tmp_path)
    (tree / "tests" / name).write_text(text, encoding="utf-8")
    run = run_trace_plugin(tree, tmp_path / "out", "collect")
    errors = run.output["collection_errors"]
    assert [error["file"] for error in errors] == [f"tests/{name}"]
    assert errors[0]["message"]
    # Files that did collect are still reported.
    assert DIRECT in {item["node_id"] for item in run.output["items"]}


@pytest.mark.network
def test_the_built_wheel_ships_the_trace_plugin(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(tmp_path)],
        cwd=repo_root,
        check=True,
        capture_output=True,
    )
    wheel = next(tmp_path.glob("*.whl"))
    with zipfile.ZipFile(wheel) as archive:
        shipped = set(archive.namelist())
    for module in sorted(path.name for path in trace_plugin_dir().glob("*.py")):
        assert f"squadron/benchmark/pytest_trace/{module}" in shipped
