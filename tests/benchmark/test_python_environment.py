"""PythonBenchmarkAdapter.resolve_environment against real uv and a scripted runner."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

from squadron.benchmark.adapter import (
    EnvironmentFailureReason,
    EnvironmentResolutionError,
    SandboxContext,
)
from squadron.benchmark.python_adapter import PythonBenchmarkAdapter
from squadron.benchmark.scrubbed_env import CredentialGrant, ScrubbedEnvironment
from squadron.core.process_runner import (
    ProcessNotFoundError,
    ProcessResult,
    ProcessTimedOutError,
    SubprocessRunner,
)
from tests.benchmark.support import RunnerCall, ScriptedRunner, git_tree

ADAPTER = PythonBenchmarkAdapter()


def context(tree: Path, tmp_path: Path, runner: object) -> SandboxContext:
    env = ScrubbedEnvironment(tmp_path / "root", "ctx", CredentialGrant.none(), {})
    return SandboxContext(
        tree=tree,
        output_dir=tmp_path / "out",
        env=env,
        runner=runner,  # type: ignore[arg-type]
        install_timeout_s=600,
        suite_timeout_s=60,
    )


@pytest.mark.network
def test_env_ok_installs_and_identifies(tmp_path: Path) -> None:
    tree = git_tree("env_ok", tmp_path)
    identity = ADAPTER.resolve_environment(context(tree, tmp_path, SubprocessRunner()))
    expected = hashlib.sha256((tree / "uv.lock").read_bytes()).hexdigest()
    assert identity.lockfile_sha256 == expected
    assert identity.interpreter_version.startswith("Python 3.")
    assert (tree / ".venv").is_dir()
    status = subprocess.run(
        ["git", "-C", str(tree), "status", "--porcelain"], capture_output=True, text=True, check=True
    )
    assert ".venv" not in status.stdout
    assert ADAPTER.path_entries(context(tree, tmp_path, None)) == (tree / ".venv" / "bin",)


@pytest.mark.network
def test_stale_lock_fails(tmp_path: Path) -> None:
    tree = git_tree("env_stale_lock", tmp_path)
    with pytest.raises(EnvironmentResolutionError) as caught:
        ADAPTER.resolve_environment(context(tree, tmp_path, SubprocessRunner()))
    assert caught.value.reason is EnvironmentFailureReason.LOCK_STALE_OR_UNRESOLVABLE
    assert "uv.lock" in caught.value.detail
    assert not (tree / ".venv").exists()


def test_no_lockfile_runs_nothing(tmp_path: Path) -> None:
    runner = ScriptedRunner(lambda call: pytest.fail("uv must not run"))
    with pytest.raises(EnvironmentResolutionError) as caught:
        ADAPTER.resolve_environment(context(git_tree("env_no_lock", tmp_path), tmp_path, runner))
    assert caught.value.reason is EnvironmentFailureReason.NO_LOCKFILE
    assert runner.calls == []


def test_foreign_lockfile_named_and_runs_nothing(tmp_path: Path) -> None:
    runner = ScriptedRunner(lambda call: pytest.fail("uv must not run"))
    tree = git_tree("env_poetry_lock", tmp_path)
    with pytest.raises(EnvironmentResolutionError) as caught:
        ADAPTER.resolve_environment(context(tree, tmp_path, runner))
    assert caught.value.reason is EnvironmentFailureReason.LOCKFILE_UNSUPPORTED
    assert "poetry.lock" in caught.value.detail
    assert runner.calls == []


def test_timeout_and_missing_uv(tmp_path: Path) -> None:
    tree = git_tree("env_ok", tmp_path)

    def times_out(call: RunnerCall) -> ProcessResult:
        raise ProcessTimedOutError(call.argv, 600)

    def missing(call: RunnerCall) -> ProcessResult:
        raise ProcessNotFoundError("uv")

    with pytest.raises(EnvironmentResolutionError) as caught:
        ADAPTER.resolve_environment(context(tree, tmp_path, ScriptedRunner(times_out)))
    assert caught.value.reason is EnvironmentFailureReason.INSTALL_TIMEOUT
    with pytest.raises(EnvironmentResolutionError) as caught:
        ADAPTER.resolve_environment(context(tree, tmp_path, ScriptedRunner(missing)))
    assert caught.value.reason is EnvironmentFailureReason.INSTALLER_MISSING
