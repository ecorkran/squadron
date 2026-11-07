"""``sq benchmark sandbox`` with the sandbox patched at the boundary."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from squadron.benchmark.adapter import (
    EnvironmentFailureReason,
    EnvironmentIdentity,
    EnvironmentResolutionError,
    FailureKind,
    NodeOutcome,
    NodeResult,
    SuiteRun,
    SuiteSelection,
)
from squadron.benchmark.scrubbed_env import MissingHarnessHomeError, MissingHarnessToolError
from squadron.cli.app import app
from squadron.metrology.snapshot_models import SourceLanguage

MODULE = "squadron.cli.commands.benchmark_sandbox"
runner = CliRunner()

IDENTITY = EnvironmentIdentity(
    language=SourceLanguage.PYTHON,
    lockfile_path="uv.lock",
    lockfile_sha256="f" * 64,
    interpreter_version="Python 3.12.1",
    installer_version="uv 0.5.0",
    platform="darwin-arm64",
    scrub_spec_version=1,
)
RUN = SuiteRun(
    (
        NodeResult("t.py::ok", NodeOutcome.PASSED),
        NodeResult("t.py::bad", NodeOutcome.FAILED, FailureKind.ASSERTION_FAILURE),
    )
)


class FakeSandbox:
    instances: list[FakeSandbox] = []
    enter_error: Exception | None = None
    events: list[str] = []

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.selections: list[SuiteSelection] = []
        self.kept = False
        self.tree, self.home, self.output_dir = Path("/t/tree"), Path("/t/home"), Path("/t/out")
        FakeSandbox.events.append("built")
        FakeSandbox.instances.append(self)

    def __enter__(self) -> FakeSandbox:
        if FakeSandbox.enter_error is not None:
            raise FakeSandbox.enter_error
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    @property
    def identity(self) -> EnvironmentIdentity:
        return IDENTITY

    def keep(self) -> None:
        self.kept = True

    def run_suite(self, selection: SuiteSelection) -> SuiteRun:
        self.selections.append(selection)
        return RUN


@pytest.fixture(autouse=True)
def patched(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    FakeSandbox.instances = []
    FakeSandbox.enter_error = None
    FakeSandbox.events = []
    monkeypatch.setattr(f"{MODULE}.BenchmarkSandbox", FakeSandbox)
    monkeypatch.setattr(
        f"{MODULE}.sweep_benchmark_orphans", lambda _runner: FakeSandbox.events.append("sweep")
    )
    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@t.invalid",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "init",
        ],
        check=True,
    )
    monkeypatch.chdir(tmp_path)


def invoke(*args: str) -> Any:
    return runner.invoke(app, ["benchmark", "sandbox", *args])


def test_prints_identity_and_sweeps_once_before_building() -> None:
    result = invoke("HEAD")
    assert result.exit_code == 0
    assert f"lockfile_sha256: {'f' * 64}" in result.stdout
    assert "identity_digest:" in result.stdout
    assert FakeSandbox.events == ["sweep", "built"]
    assert FakeSandbox.instances[0].selections == []


def test_suite_prints_counts_and_failing_nodes() -> None:
    result = invoke("HEAD", "--suite")
    assert "outcomes: failed=1, passed=1" in result.stdout
    assert "failure kinds: assertion_failure=1" in result.stdout
    assert "failed t.py::bad (assertion_failure)" in result.stdout
    assert FakeSandbox.instances[0].selections == [SuiteSelection.all_tests()]


def test_node_passes_only_those_ids() -> None:
    invoke("HEAD", "--node", "t.py::a", "--node", "t.py::b")
    assert FakeSandbox.instances[0].selections == [SuiteSelection.nodes(("t.py::a", "t.py::b"))]


def test_suite_with_node_is_a_usage_error() -> None:
    assert invoke("HEAD", "--suite", "--node", "t.py::a").exit_code == 2


def test_keep_prints_the_paths() -> None:
    result = invoke("HEAD", "--keep")
    assert FakeSandbox.instances[0].kept
    assert "tree: /t/tree" in result.stdout
    assert "home: /t/home" in result.stdout
    assert "out: /t/out" in result.stdout


def test_resolution_failure_prints_reason_and_stderr() -> None:
    FakeSandbox.enter_error = EnvironmentResolutionError(
        EnvironmentFailureReason.LOCK_STALE_OR_UNRESOLVABLE, "uv says the lock is stale"
    )
    result = invoke("HEAD")
    assert result.exit_code == 1
    assert "lock_stale_or_unresolvable" in result.stderr
    assert "uv says the lock is stale" in result.stderr


def test_bad_rev_exits_one_before_any_sweep() -> None:
    result = invoke("no-such-rev")
    assert result.exit_code == 1
    assert "rev-parse" in result.stderr
    assert FakeSandbox.events == []


@pytest.mark.parametrize("error", [MissingHarnessHomeError(), MissingHarnessToolError("uv")])
def test_missing_home_or_tool_exits_one_without_a_traceback(error: Exception) -> None:
    FakeSandbox.enter_error = error
    result = invoke("HEAD")
    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit) or result.exception is None
    assert str(error) in result.stderr
