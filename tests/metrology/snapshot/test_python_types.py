"""Python adapter: uv environment gate and pyright type errors (slice 400, D7, D8)."""

from __future__ import annotations

import logging
import stat
from pathlib import Path

import pytest

from squadron.metrology.snapshot.contract import ToolResult
from squadron.metrology.snapshot.python_types import (
    measure_pyright_types,
    resolve_pyright_rule_set,
)
from squadron.metrology.snapshot_models import (
    RULE_SET_SOURCE_TOOL_DEFAULTS,
    AbsenceReason,
    Measurement,
)
from tests.metrology.snapshot.builders import make_context, read_fixture
from tests.metrology.snapshot.conftest import FakeToolRunner

LOCK_BYTES = b"version = 1\n"


def executable(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


class Env:
    """A repo with uv.lock, a venv, and fake uv and pyright binaries, plus a scripted runner."""

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.repo = tmp_path / "repo"
        self.repo.mkdir()
        (self.repo / "uv.lock").write_bytes(LOCK_BYTES)
        self.python = executable(self.repo / ".venv" / "bin" / "python")
        self.pyright = executable(self.repo / ".venv" / "bin" / "pyright")
        self.uv = executable(tmp_path / "bin" / "uv")
        monkeypatch.setenv("PATH", str(tmp_path / "bin"))
        self.runner = FakeToolRunner()
        self.script_ok()

    def script_ok(self) -> None:
        self.runner.script((str(self.uv), "sync"), ToolResult(0, "", "", False))
        self.runner.script((str(self.python), "--version"), ToolResult(0, "Python 3.12.4\n", "", False))
        self.runner.script(
            (str(self.pyright), "--version"),
            ToolResult(0, read_fixture("version_pyright.stdout", self.repo), "", False),
        )
        self.report("pyright_scratch_findings.stdout", exit_code=1)

    def report(self, fixture: str, exit_code: int) -> None:
        self.runner.script(
            (str(self.pyright), "--outputjson"),
            ToolResult(exit_code, read_fixture(fixture, self.repo), "", False),
        )

    def measure(self, caplog: pytest.LogCaptureFixture | None = None) -> Measurement:
        ctx = make_context(self.repo, self.runner)
        if caplog is None:
            return measure_pyright_types(ctx, ["mod.py"])
        with caplog.at_level(logging.WARNING):
            return measure_pyright_types(ctx, ["mod.py"])


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Env:
    return Env(tmp_path, monkeypatch)


def assert_absent(
    measurement: Measurement,
    reason: AbsenceReason,
    detail: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    assert measurement.absent is reason
    assert detail in (measurement.absent_detail or "")
    assert any(r.levelno == logging.WARNING for r in caplog.records)


class TestMeasured:
    def test_in_sync_environment_counts_only_errors(self, env: Env) -> None:
        measurement = env.measure()

        # The captured report holds one error and one warning in mod.py.
        assert measurement.absent is None
        assert measurement.per_file == {"mod.py": 1}
        assert measurement.tool is not None
        assert (measurement.tool.name, measurement.tool.version) == ("pyright", "1.1.408")

    def test_environment_identity_carries_lockfile_hash_and_interpreter(self, env: Env) -> None:
        import hashlib

        measurement = env.measure()

        assert measurement.environment is not None
        assert measurement.environment.lockfile_path == "uv.lock"
        assert measurement.environment.lockfile_sha256 == hashlib.sha256(LOCK_BYTES).hexdigest()
        assert measurement.environment.interpreter_version == "3.12.4"

    def test_clean_run_is_present_with_no_files_listed(self, env: Env) -> None:
        env.report("pyright_squadron_clean.stdout", exit_code=0)

        measurement = env.measure()

        assert measurement.absent is None
        assert measurement.per_file == {}

    def test_pyright_runs_with_the_venv_interpreter_over_the_explicit_files(self, env: Env) -> None:
        env.measure()

        run = next(call for call in env.runner.calls if "--outputjson" in call)
        assert run[1:] == ("--outputjson", "--pythonpath", str(env.python), "mod.py")

    def test_counting_states_that_pyright_include_is_ignored(self, env: Env) -> None:
        measurement = env.measure()

        assert measurement.tool is not None
        assert "regardless of pyright's own include" in measurement.tool.counting


class TestEnvironmentUnresolved:
    def test_no_lockfile(self, env: Env, caplog: pytest.LogCaptureFixture) -> None:
        (env.repo / "uv.lock").unlink()

        assert_absent(
            env.measure(caplog), AbsenceReason.ENVIRONMENT_UNRESOLVED, "uv.lock not found", caplog
        )

    def test_other_lockfile_type_is_named(self, env: Env, caplog: pytest.LogCaptureFixture) -> None:
        (env.repo / "uv.lock").unlink()
        (env.repo / "poetry.lock").write_text("x", encoding="utf-8")

        assert_absent(
            env.measure(caplog),
            AbsenceReason.ENVIRONMENT_UNRESOLVED,
            "lockfile type not supported: poetry.lock",
            caplog,
        )

    def test_no_venv(self, env: Env, caplog: pytest.LogCaptureFixture) -> None:
        for path in sorted(env.repo.joinpath(".venv").rglob("*"), reverse=True):
            path.unlink() if path.is_file() else path.rmdir()
        env.repo.joinpath(".venv").rmdir()

        assert_absent(
            env.measure(caplog), AbsenceReason.ENVIRONMENT_UNRESOLVED, ".venv not found", caplog
        )
        assert not [c for c in env.runner.calls if c[0] == str(env.uv)]

    def test_uv_reports_the_environment_out_of_date(
        self, env: Env, caplog: pytest.LogCaptureFixture
    ) -> None:
        stderr = read_fixture("uv_out_of_sync.stderr", env.repo)
        env.runner.script((str(env.uv), "sync"), ToolResult(1, "", stderr, False))

        assert_absent(env.measure(caplog), AbsenceReason.ENVIRONMENT_UNRESOLVED, "out of sync", caplog)

    def test_uv_missing(
        self, env: Env, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PATH", str(env.repo / "empty"))

        assert_absent(env.measure(caplog), AbsenceReason.TOOL_MISSING, "uv not found", caplog)

    def test_uv_timeout(self, env: Env, caplog: pytest.LogCaptureFixture) -> None:
        env.runner.script((str(env.uv), "sync"), ToolResult(-1, "", "", True))

        assert_absent(env.measure(caplog), AbsenceReason.TOOL_FAILED, "uv timed out", caplog)

    def test_uv_unexpected_exit(self, env: Env, caplog: pytest.LogCaptureFixture) -> None:
        env.runner.script((str(env.uv), "sync"), ToolResult(2, "", "error: no lock", False))

        assert_absent(env.measure(caplog), AbsenceReason.TOOL_FAILED, "uv exited 2", caplog)

    def test_venv_interpreter_version_unreadable(
        self, env: Env, caplog: pytest.LogCaptureFixture
    ) -> None:
        env.runner.script((str(env.python), "--version"), ToolResult(1, "", "", False))

        assert_absent(
            env.measure(caplog), AbsenceReason.TOOL_FAILED, "can't read the .venv/bin/python", caplog
        )


class TestPyrightFailureModes:
    def test_missing_tool(self, env: Env, caplog: pytest.LogCaptureFixture) -> None:
        env.pyright.unlink()

        assert_absent(env.measure(caplog), AbsenceReason.TOOL_MISSING, "pyright not found", caplog)

    def test_version_probe_failure_means_pyright_is_not_run(
        self, env: Env, caplog: pytest.LogCaptureFixture
    ) -> None:
        env.runner.script((str(env.pyright), "--version"), ToolResult(2, "", "boom", False))

        assert_absent(env.measure(caplog), AbsenceReason.TOOL_FAILED, "version probe failed", caplog)
        assert not [c for c in env.runner.calls if "--outputjson" in c]

    def test_timeout(self, env: Env, caplog: pytest.LogCaptureFixture) -> None:
        env.runner.script((str(env.pyright), "--outputjson"), ToolResult(-1, "", "", True))

        assert_absent(env.measure(caplog), AbsenceReason.TOOL_FAILED, "timed out", caplog)

    def test_bad_json(self, env: Env, caplog: pytest.LogCaptureFixture) -> None:
        env.runner.script((str(env.pyright), "--outputjson"), ToolResult(0, "not json", "", False))

        assert_absent(env.measure(caplog), AbsenceReason.TOOL_FAILED, "isn't valid JSON", caplog)

    def test_fatal_exit_is_a_failure_even_though_stdout_is_a_valid_empty_report(
        self, env: Env, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Exit 3 (unparseable config) still prints a well-formed zero-error JSON report."""
        env.report("pyright_fatal_config.stdout", exit_code=3)

        measurement = env.measure(caplog)

        assert_absent(measurement, AbsenceReason.TOOL_FAILED, "pyright exited 3", caplog)
        assert measurement.per_file == {}


class TestPyrightRuleSet:
    def test_pyrightconfig_then_pyproject_then_defaults(self, tmp_path: Path) -> None:
        assert resolve_pyright_rule_set(tmp_path).source == RULE_SET_SOURCE_TOOL_DEFAULTS
        assert resolve_pyright_rule_set(tmp_path).content_hash is None

        (tmp_path / "pyproject.toml").write_text("[tool.pyright]\nstrict = ['src']\n")
        assert resolve_pyright_rule_set(tmp_path).source == "pyproject.toml[tool.pyright]"

        (tmp_path / "pyrightconfig.json").write_text("{}", encoding="utf-8")
        assert resolve_pyright_rule_set(tmp_path).source == "pyrightconfig.json"

    def test_a_version_bump_does_not_change_the_pyproject_table_hash(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nversion = "1"\n[tool.pyright]\nstrict = ["src"]\n')
        before = resolve_pyright_rule_set(tmp_path).content_hash

        pyproject.write_text('[project]\nversion = "2"\n[tool.pyright]\nstrict = ["src"]\n')

        assert resolve_pyright_rule_set(tmp_path).content_hash == before
