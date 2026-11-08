"""``PythonFixCaseAdapter.trace`` in a real sandbox (slice 422 D6, D7). ``network`` installs."""

from __future__ import annotations

import logging
import os
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from squadron.benchmark.adapter import SandboxContext
from squadron.benchmark.fairness import AllowedBoundary, HarnessFailure
from squadron.benchmark.python_adapter import PythonBenchmarkAdapter
from squadron.benchmark.python_fairness import OUTPUT_FILE, PythonFixCaseAdapter
from squadron.benchmark.sandbox import BenchmarkSandbox
from squadron.benchmark.scrubbed_env import CredentialGrant, ScrubbedEnvironment
from squadron.core.process_runner import ProcessResult, ProcessTimedOutError, SubprocessRunner
from squadron.metrology.benchmark_models import TestRejection
from tests.benchmark.support import RunnerCall, ScriptedRunner, git_tree

ADAPTER = PythonFixCaseAdapter()
STATIC = "tests/test_boundary_static.py::"
PATCHES = "tests/test_boundary_patches.py::"


@pytest.fixture(scope="module")
def context(tmp_path_factory: pytest.TempPathFactory) -> Iterator[SandboxContext]:
    tree = git_tree("fixfair_project", tmp_path_factory.mktemp("trace_src"))
    head = subprocess.run(
        ["git", "-C", str(tree), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    sandbox = BenchmarkSandbox(
        start_sha=head,
        sandbox_id="trace-project",
        repo_root=tree,
        runner=SubprocessRunner(),
        adapter=PythonBenchmarkAdapter(),
        harness_env=dict(os.environ),
        install_timeout_s=900,
        suite_timeout_s=300,
        root=tmp_path_factory.mktemp("trace_root"),
    )
    with sandbox:
        yield sandbox.context()


@pytest.mark.network
def test_traced_tests_get_the_expected_verdicts(context: SandboxContext) -> None:
    allowed = ADAPTER.boundary(context)
    ids = [
        f"{STATIC}test_drives_the_cli_entry_point",
        f"{STATIC}test_ref_exported_function",
        f"{STATIC}test_ref_internal_function",
        f"{STATIC}test_ref_non_exported_class",
        f"{STATIC}test_ref_project_module_object",
        f"{PATCHES}test_patch_project_module_by_string",
        f"{PATCHES}test_patch_foreign_subprocess_run",
    ]
    verdicts = ADAPTER.trace(context, ids, allowed)

    assert verdicts[ids[0]].rejection is None, "driving the script target qualifies"
    assert verdicts[ids[1]].rejection is None
    assert verdicts[ids[2]].rejection is TestRejection.REACHES_PAST_BOUNDARY
    assert verdicts[ids[2]].detail == "fixpkg.internal.internal_function"
    assert verdicts[ids[3]].rejection is TestRejection.REACHES_PAST_BOUNDARY
    assert verdicts[ids[3]].detail == "fixpkg.internal.InternalWidget"
    assert verdicts[ids[4]].rejection is TestRejection.REACHES_PAST_BOUNDARY, (
        "module ref plus internal call"
    )
    assert verdicts[ids[5]].rejection is TestRejection.PATCHES_PROJECT_CODE
    assert verdicts[ids[5]].detail == "fixpkg.mod.run"
    assert verdicts[ids[6]].rejection is None, "patching a foreign module is allowed"


@pytest.mark.network
def test_a_node_the_run_does_not_report_is_a_harness_failure(context: SandboxContext) -> None:
    allowed = ADAPTER.boundary(context)
    with pytest.raises(HarnessFailure):
        ADAPTER.trace(context, ["tests/no_such_file.py::test_nothing"], allowed)


# --- Scripted failure modes ---------------------------------------------------------------


def scripted_context(tmp_path: Path, trace_step: object) -> SandboxContext:
    """A context whose runner lists one test file, then does ``trace_step`` for pytest."""

    def handler(call: RunnerCall) -> ProcessResult:
        if call.argv[:2] == ("git", "ls-files"):
            return ProcessResult(call.argv, 0, "tests/test_a.py\n", "")
        if isinstance(trace_step, Exception):
            raise trace_step
        return ProcessResult(call.argv, 0, "", "no plugin")

    return SandboxContext(
        tree=tmp_path,
        output_dir=tmp_path,
        env=ScrubbedEnvironment(tmp_path, "x", CredentialGrant.none(), {}),
        runner=ScriptedRunner(handler),
        install_timeout_s=1,
        suite_timeout_s=1,
    )


def test_a_trace_timeout_is_a_harness_failure(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    ctx = scripted_context(tmp_path, ProcessTimedOutError(["pytest"], 1))
    with caplog.at_level(logging.ERROR), pytest.raises(HarnessFailure, match="exceeded"):
        ADAPTER.trace(ctx, ["tests/test_a.py::t"], AllowedBoundary())
    assert any(record.levelno == logging.ERROR for record in caplog.records)


def test_a_missing_trace_output_is_a_harness_failure(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    ctx = scripted_context(tmp_path, None)
    assert not (tmp_path / OUTPUT_FILE).exists()
    with caplog.at_level(logging.ERROR), pytest.raises(HarnessFailure, match="never loaded"):
        ADAPTER.trace(ctx, ["tests/test_a.py::t"], AllowedBoundary())
    assert any(record.levelno == logging.ERROR for record in caplog.records)
