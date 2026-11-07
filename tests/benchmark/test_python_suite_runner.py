"""run_suite with a scripted ProcessRunner: command line, env, and report handling."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from squadron.benchmark.adapter import (
    FailureKind,
    NodeOutcome,
    SandboxContext,
    SuiteRunError,
    SuiteSelection,
)
from squadron.benchmark.python_adapter import PythonBenchmarkAdapter
from squadron.benchmark.python_failure import REPORT_KEYS, REPORT_PATH_ENV
from squadron.benchmark.scrubbed_env import CredentialGrant, ScrubbedEnvironment
from squadron.core.process_runner import ProcessResult, ProcessTimedOutError
from tests.benchmark.support import RunnerCall, ScriptedRunner

ADAPTER = PythonBenchmarkAdapter()
NODE = "tests/test_a.py::test_one"


def line(node: str, phase: str, outcome: str, **fields: Any) -> dict[str, Any]:
    record: dict[str, Any] = dict.fromkeys(REPORT_KEYS)
    record.update(node_id=node, phase=phase, outcome=outcome)
    record.update(fields)
    return record


def passing(node: str = NODE) -> list[dict[str, Any]]:
    return [
        line(node, "setup", "passed"),
        line(node, "call", "passed"),
        line(node, "teardown", "passed"),
    ]


def runner_writing(
    lines: list[dict[str, Any]] | str | None, exit_code: int, stderr: str = ""
) -> ScriptedRunner:
    def handler(call: RunnerCall) -> ProcessResult:
        assert call.env is not None
        if lines is not None:
            text = lines if isinstance(lines, str) else "".join(json.dumps(r) + "\n" for r in lines)
            Path(call.env[REPORT_PATH_ENV]).write_text(text, encoding="utf-8")
        return ProcessResult(call.argv, exit_code, "", stderr)

    return ScriptedRunner(handler)


@pytest.fixture
def make_ctx(tmp_path: Path) -> Callable[[ScriptedRunner], SandboxContext]:
    def build(runner: ScriptedRunner) -> SandboxContext:
        tree = tmp_path / "tree"
        tree.mkdir(exist_ok=True)
        harness = {"HOME": str(tmp_path), "PATH": "/usr/bin", "GH_TOKEN": "secret", "LANG": "C"}
        env = ScrubbedEnvironment(tmp_path / "root", "sb", CredentialGrant.none(), harness)
        return SandboxContext(tree, tmp_path / "out", env, runner, 60, 30)

    return build


def test_command_line_and_environment(make_ctx: Callable[[ScriptedRunner], SandboxContext]) -> None:
    runner = runner_writing(passing(), 0)
    ctx = make_ctx(runner)
    ADAPTER.run_suite(ctx, SuiteSelection.nodes((NODE,), deselect=("tests/x.py::skip",)))
    call = runner.calls[0]
    assert call.argv[1:4] == ("-m", "pytest", "-p")
    assert "squadron_benchmark_reporter" in call.argv
    assert "no:cacheprovider" in call.argv
    assert call.argv[-1] == NODE
    assert call.argv[call.argv.index("--deselect") + 1] == "tests/x.py::skip"
    assert call.replace_env is True
    assert call.timeout == 30
    assert call.env is not None
    assert "GH_TOKEN" not in call.env
    assert call.env["PYTHONPATH"].endswith("plugin")
    assert call.env[REPORT_PATH_ENV].endswith("report.jsonl")
    assert call.env["PATH"].split(":")[0].endswith(".venv/bin")
    assert (Path(call.env["PYTHONPATH"]) / "squadron_benchmark_reporter.py").is_file()
    assert not list(ctx.tree.iterdir())


def test_all_tests_selection_has_no_node_ids(
    make_ctx: Callable[[ScriptedRunner], SandboxContext],
) -> None:
    runner = runner_writing(passing(), 0)
    run = ADAPTER.run_suite(make_ctx(runner), SuiteSelection.all_tests(deselect=("a::b",)))
    assert runner.calls[0].argv[-2:] == ("--deselect", "a::b")
    assert [r.node_id for r in run.results] == [NODE]


@pytest.mark.parametrize(
    ("lines", "exit_code"), [(None, 0), (None, 1), ("{not json\n", 1), ("", 0), ("", 1)]
)
def test_unusable_report_raises(
    make_ctx: Callable[[ScriptedRunner], SandboxContext],
    lines: str | None,
    exit_code: int,
) -> None:
    runner = runner_writing(lines, exit_code, stderr="pytest said no")
    with pytest.raises(SuiteRunError, match="pytest"):
        ADAPTER.run_suite(make_ctx(runner), SuiteSelection.all_tests())


def test_empty_report_with_exit_5_means_nothing_collected(
    make_ctx: Callable[[ScriptedRunner], SandboxContext],
) -> None:
    run = ADAPTER.run_suite(make_ctx(runner_writing("", 5)), SuiteSelection.all_tests())
    assert run.results == ()
    assert not run.timed_out


def test_empty_report_with_exit_4_marks_each_requested_id_uncollected(
    make_ctx: Callable[[ScriptedRunner], SandboxContext],
) -> None:
    run = ADAPTER.run_suite(make_ctx(runner_writing("", 4)), SuiteSelection.nodes(("a::x", "b::y")))
    assert [(r.node_id, r.outcome, r.failure_kind) for r in run.results] == [
        ("a::x", NodeOutcome.ERROR, FailureKind.COLLECTION_ERROR),
        ("b::y", NodeOutcome.ERROR, FailureKind.COLLECTION_ERROR),
    ]


def test_requested_id_without_record_is_collection_error_or_takes_file_error(
    make_ctx: Callable[[ScriptedRunner], SandboxContext],
) -> None:
    records = [*passing(), line("tests/bad.py", "collect", "failed", exc_type="ImportError")]
    run = ADAPTER.run_suite(
        make_ctx(runner_writing(records, 1)),
        SuiteSelection.nodes((NODE, "tests/bad.py::test_z", "tests/other.py::test_q")),
    )
    by_id = {r.node_id: r for r in run.results}
    assert by_id[NODE].outcome is NodeOutcome.PASSED
    assert by_id["tests/bad.py::test_z"].exception_type == "ImportError"
    assert by_id["tests/other.py::test_q"].failure_kind is FailureKind.COLLECTION_ERROR


def test_timeout_keeps_reported_nodes_and_marks_the_rest_not_run(
    make_ctx: Callable[[ScriptedRunner], SandboxContext],
) -> None:
    def handler(call: RunnerCall) -> ProcessResult:
        assert call.env is not None
        records = [*passing(), line("tests/slow.py::test_s", "setup", "passed")]
        Path(call.env[REPORT_PATH_ENV]).write_text(
            "".join(json.dumps(r) + "\n" for r in records), encoding="utf-8"
        )
        raise ProcessTimedOutError(call.argv, 30)

    run = ADAPTER.run_suite(
        make_ctx(ScriptedRunner(handler)),
        SuiteSelection.nodes((NODE, "tests/slow.py::test_s", "tests/never.py::test_n")),
    )
    assert run.timed_out
    assert [r.outcome for r in run.results] == [
        NodeOutcome.PASSED,
        NodeOutcome.NOT_RUN,
        NodeOutcome.NOT_RUN,
    ]


def test_timeout_drops_a_truncated_final_line(
    make_ctx: Callable[[ScriptedRunner], SandboxContext],
) -> None:
    def handler(call: RunnerCall) -> ProcessResult:
        assert call.env is not None
        complete = "".join(json.dumps(r) + "\n" for r in passing())
        Path(call.env[REPORT_PATH_ENV]).write_text(
            complete + '{"node_id": "tests/slo', encoding="utf-8"
        )
        raise ProcessTimedOutError(call.argv, 30)

    run = ADAPTER.run_suite(make_ctx(ScriptedRunner(handler)), SuiteSelection.all_tests())
    assert run.timed_out
    assert [r.node_id for r in run.results] == [NODE]


def test_truncated_line_without_a_timeout_still_raises(
    make_ctx: Callable[[ScriptedRunner], SandboxContext],
) -> None:
    runner = runner_writing('{"node_id": "tests/slo', 0)
    with pytest.raises(SuiteRunError):
        ADAPTER.run_suite(make_ctx(runner), SuiteSelection.all_tests())
