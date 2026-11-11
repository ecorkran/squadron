"""PythonFixCaseAdapter: test-side rules and collection (slice 422 D3).

Tests that install a project carry the ``network`` marker.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from squadron.benchmark.adapter import SandboxContext
from squadron.benchmark.fairness import CollectedTests, CollectionFailed, HarnessFailure
from squadron.benchmark.python_adapter import PythonBenchmarkAdapter
from squadron.benchmark.python_fairness import OUTPUT_FILE, PythonFixCaseAdapter
from squadron.benchmark.sandbox import BenchmarkSandbox
from squadron.benchmark.scrubbed_env import CredentialGrant, ScrubbedEnvironment
from squadron.benchmark.test_sets import sort_tests
from squadron.core.process_runner import (
    ProcessNotFoundError,
    ProcessResult,
    ProcessTimedOutError,
    SubprocessRunner,
)
from squadron.metrology.benchmark_models import ConftestFixture
from tests.benchmark.support import FixHistory, RunnerCall, ScriptedRunner, failed, fix_history, ok

ADAPTER = PythonFixCaseAdapter()
PYTHON_ADAPTER = PythonBenchmarkAdapter()


def sandbox_at(history: FixHistory, sha: str, root: Path, sandbox_id: str) -> BenchmarkSandbox:
    return BenchmarkSandbox(
        start_sha=sha,
        sandbox_id=sandbox_id,
        repo_root=history.repo,
        runner=SubprocessRunner(),
        adapter=PYTHON_ADAPTER,
        harness_env=dict(os.environ),
        install_timeout_s=900,
        suite_timeout_s=300,
        root=root,
    )


@pytest.fixture(scope="module")
def sort_sets(tmp_path_factory: pytest.TempPathFactory) -> FixHistory:
    return fix_history("fixfair_project", "sort_sets", tmp_path_factory.mktemp("sort_sets"))


@pytest.fixture(scope="module")
def parent_context(
    sort_sets: FixHistory, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[SandboxContext]:
    root = tmp_path_factory.mktemp("parent_root")
    with sandbox_at(sort_sets, sort_sets.parent_sha, root, "fair-parent") as sandbox:
        yield sandbox.context()


@pytest.fixture(scope="module")
def reference_context(
    sort_sets: FixHistory, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[SandboxContext]:
    root = tmp_path_factory.mktemp("reference_root")
    with sandbox_at(sort_sets, sort_sets.fix_sha, root, "fair-reference") as sandbox:
        yield sandbox.context()


@pytest.mark.network
def test_collect_at_parent_and_reference_sorts_into_the_expected_sets(
    parent_context: SandboxContext, reference_context: SandboxContext
) -> None:
    sets = sort_tests(ADAPTER.collect(parent_context), ADAPTER.collect(reference_context))
    assert sets.hidden_candidates == (
        "tests/test_new_feature.py::test_new_behavior",
        "tests/test_reach.py::test_direct_body",
    )
    assert sets.superseded == (
        "tests/test_other.py::test_unrelated",
        "tests/test_reach.py::test_direct_body",
    )
    assert "tests/test_reach.py::test_uses_helper_chain" in sets.unchanged
    assert sets.hidden_fixtures == (
        ConftestFixture(conftest_path="tests/conftest.py", fixture_name="extra_value"),
    )


@pytest.mark.network
def test_collect_reports_the_fixtures_each_node_reaches(reference_context: SandboxContext) -> None:
    collected = ADAPTER.collect(reference_context)
    reached = collected.fixtures_reached["tests/test_new_feature.py::test_new_behavior"]
    assert reached == (ConftestFixture(conftest_path="tests/conftest.py", fixture_name="extra_value"),)


@pytest.mark.network
def test_a_broken_test_file_at_the_reference_raises_collection_failed(
    tmp_path: Path,
) -> None:
    history = fix_history("fixfair_project", "collection_broken", tmp_path / "history")
    with sandbox_at(history, history.fix_sha, tmp_path / "root", "fair-broken") as sandbox:
        with pytest.raises(CollectionFailed) as caught:
            ADAPTER.collect(sandbox.context())
    assert caught.value.file == "tests/test_broken.py"


# --- Scripted failure modes: each is an ERROR log plus HarnessFailure --------------


def scripted_context(tmp_path: Path, handler: object) -> SandboxContext:
    tree, out = tmp_path / "tree", tmp_path / "out"
    tree.mkdir()
    out.mkdir()
    return SandboxContext(
        tree=tree,
        output_dir=out,
        env=ScrubbedEnvironment(tmp_path, "scripted", CredentialGrant.none(), {}),
        runner=ScriptedRunner(handler),  # type: ignore[arg-type]
        install_timeout_s=1,
        suite_timeout_s=1,
    )


def pytest_step(call: RunnerCall, ctx_out: Path, *, write: str | None, code: int = 0) -> ProcessResult:
    if write is not None:
        (ctx_out / OUTPUT_FILE).write_text(write, encoding="utf-8")
    return ProcessResult(call.argv, code, "", "pytest said something")


def run_collect(tmp_path: Path, on_pytest: object) -> CollectedTests:
    def handler(call: RunnerCall) -> ProcessResult:
        if call.argv[:2] == ("git", "ls-files"):
            return ok(call.argv, stdout="tests/test_a.py\n")
        return on_pytest(call)  # type: ignore[operator]

    return ADAPTER.collect(scripted_context(tmp_path, handler))


def test_a_pytest_timeout_is_a_harness_failure(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    def on_pytest(call: RunnerCall) -> ProcessResult:
        raise ProcessTimedOutError(call.argv, 1)

    with caplog.at_level(logging.ERROR), pytest.raises(HarnessFailure, match="exceeded"):
        run_collect(tmp_path, on_pytest)
    assert any(record.levelno == logging.ERROR for record in caplog.records)


def test_a_missing_output_file_is_a_harness_failure_naming_stderr(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    def on_pytest(call: RunnerCall) -> ProcessResult:
        return ProcessResult(call.argv, 0, "", "pytest said something")

    with caplog.at_level(logging.ERROR), pytest.raises(HarnessFailure, match="never loaded") as caught:
        run_collect(tmp_path, on_pytest)
    assert "pytest said something" in caught.value.detail
    assert any(record.levelno == logging.ERROR for record in caplog.records)


def test_unparsable_output_is_a_harness_failure(tmp_path: Path) -> None:
    def on_pytest(call: RunnerCall) -> ProcessResult:
        return pytest_step(call, tmp_path / "out", write="{not json")

    with pytest.raises(HarnessFailure, match="does not parse"):
        run_collect(tmp_path, on_pytest)


def test_an_unexpected_pytest_exit_code_is_a_harness_failure(tmp_path: Path) -> None:
    def on_pytest(call: RunnerCall) -> ProcessResult:
        return pytest_step(call, tmp_path / "out", write='{"items": []}', code=4)

    with pytest.raises(HarnessFailure, match="exited 4"):
        run_collect(tmp_path, on_pytest)


def test_a_missing_pytest_executable_is_a_harness_failure(tmp_path: Path) -> None:
    def on_pytest(call: RunnerCall) -> ProcessResult:
        raise ProcessNotFoundError(call.argv[0])

    with pytest.raises(HarnessFailure, match="not found"):
        run_collect(tmp_path, on_pytest)


def test_a_failing_git_ls_files_is_a_harness_failure(tmp_path: Path) -> None:
    def handler(call: RunnerCall) -> ProcessResult:
        return failed(call.argv, code=128, stderr="fatal: not a git repository")

    with pytest.raises(HarnessFailure, match="not a git repository"):
        ADAPTER.collect(scripted_context(tmp_path, handler))


def test_a_valid_scripted_output_is_folded_into_collected_tests(tmp_path: Path) -> None:
    payload = (
        '{"items": [{"node_id": "tests/test_a.py::t", "digest": "d", '
        '"fixtures": [["tests/conftest.py", "f"]]}], '
        '"conftest_fixtures": [["tests/conftest.py", "f"]], "collection_errors": []}'
    )

    def on_pytest(call: RunnerCall) -> ProcessResult:
        return pytest_step(call, tmp_path / "out", write=payload)

    collected = run_collect(tmp_path, on_pytest)
    fixture = ConftestFixture(conftest_path="tests/conftest.py", fixture_name="f")
    assert collected.digests == {"tests/test_a.py::t": "d"}
    assert collected.fixtures_reached == {"tests/test_a.py::t": (fixture,)}
    assert collected.conftest_fixtures == (fixture,)


def test_the_pytest_argv_matches_the_documented_command(tmp_path: Path) -> None:
    seen: list[RunnerCall] = []

    def on_pytest(call: RunnerCall) -> ProcessResult:
        seen.append(call)
        return pytest_step(
            call,
            tmp_path / "out",
            write='{"items": [], "conftest_fixtures": [], "collection_errors": []}',
            code=5,
        )

    run_collect(tmp_path, on_pytest)
    argv = seen[0].argv
    assert argv[0].endswith(".venv/bin/python")
    assert argv[1:4] == ("-m", "pytest", "-p")
    assert "squadron_fixcase_trace" in argv and "--collect-only" in argv
    assert seen[0].replace_env is True


# --- is_test_side (D3) ------------------------------------------------------------

TESTPATHS_TEXT = '[tool.pytest.ini_options]\ntestpaths = ["checks", "more/specs"]\n'


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("tests/test_a.py", True),
        ("tests/data/case.json", True),
        ("test/helper.py", True),
        ("pkg/tests/inner/test_b.py", True),
        ("src/pkg/test_widget.py", True),
        ("src/pkg/widget_test.py", True),
        ("conftest.py", True),
        ("src/pkg/widget.py", False),
        ("docs/testing.md", False),
        ("src/latest/mod.py", False),
    ],
)
def test_default_rules_without_testpaths(path: str, expected: bool) -> None:
    assert ADAPTER.is_test_side(None, path) is expected
    assert ADAPTER.is_test_side("[project]\nname = 'x'\n", path) is expected


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("checks/test_a.py", True),
        ("checks/helpers/util.py", True),
        ("more/specs/test_b.py", True),
        ("tests/test_a.py", False),
        ("conftest.py", False),
        ("checks_extra/test_c.py", False),
    ],
)
def test_testpaths_replace_the_defaults(path: str, expected: bool) -> None:
    assert ADAPTER.is_test_side(TESTPATHS_TEXT, path) is expected


def test_testpaths_as_a_space_separated_string() -> None:
    text = '[tool.pytest.ini_options]\ntestpaths = "checks specs"\n'
    assert ADAPTER.is_test_side(text, "specs/test_x.py") is True
    assert ADAPTER.is_test_side(text, "tests/test_x.py") is False


def test_an_unparsable_pyproject_is_a_harness_failure(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.ERROR), pytest.raises(HarnessFailure, match="does not parse"):
        ADAPTER.is_test_side("[broken", "tests/test_a.py")
    assert "does not parse" in caplog.text


def test_source_and_lockfile_hooks() -> None:
    assert ADAPTER.is_test_source("tests/test_a.py") is True
    assert ADAPTER.is_test_source("tests/data.json") is False
    assert ADAPTER.lockfile_names() == ("uv.lock",)
