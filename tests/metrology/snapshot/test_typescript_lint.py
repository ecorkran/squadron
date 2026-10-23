"""TypeScript adapter: ESLint lint count (slice 400, D4, D5, D8)."""

from __future__ import annotations

import hashlib
import json
import logging
import stat
from pathlib import Path

import pytest

from squadron.metrology.snapshot.contract import ToolResult
from squadron.metrology.snapshot.typescript_lint import (
    measure_eslint_lint,
    resolve_eslint_rule_set,
)
from squadron.metrology.snapshot_models import AbsenceReason, Measurement
from tests.metrology.snapshot.builders import make_context, read_fixture
from tests.metrology.snapshot.conftest import FakeToolRunner

CONFIG_BYTES = b"export default [];\n"
FINDINGS_FILE = "packages/core/src/project-defaults.ts"
IGNORED_FILE = "packages/core/vitest.config.ts"


def executable(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


class Env:
    """A repo with an ESLint config and a fake project eslint, plus a scripted runner."""

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PATH", str(tmp_path / "no-tools-here"))
        self.repo = tmp_path / "repo"
        self.repo.mkdir()
        (self.repo / "eslint.config.mjs").write_bytes(CONFIG_BYTES)
        self.eslint = executable(self.repo / "node_modules" / ".bin" / "eslint")
        self.runner = FakeToolRunner()
        self.runner.script(
            (str(self.eslint), "--version"),
            ToolResult(0, read_fixture("version_eslint.stdout", self.repo), "", False),
        )
        self.report("eslint_context_forge_findings.stdout", exit_code=1)

    def report(self, fixture: str, exit_code: int, stderr: str = "") -> None:
        self.runner.script(
            (str(self.eslint), "--format"),
            ToolResult(exit_code, read_fixture(fixture, self.repo), stderr, False),
        )

    def measure(self, files: list[str], caplog: pytest.LogCaptureFixture | None = None) -> Measurement:
        ctx = make_context(self.repo, self.runner)
        if caplog is None:
            return measure_eslint_lint(ctx, files)
        with caplog.at_level(logging.WARNING):
            return measure_eslint_lint(ctx, files)


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
    assert measurement.per_file == {}
    assert any(r.levelno == logging.WARNING for r in caplog.records)


class TestMeasured:
    def test_exit_1_with_findings_is_counted_not_failed(self, env: Env) -> None:
        captured = json.loads(read_fixture("eslint_context_forge_findings.stdout", env.repo))
        expected = len(captured[0]["messages"])

        measurement = env.measure([FINDINGS_FILE])

        assert measurement.absent is None
        assert expected >= 2
        assert measurement.per_file == {FINDINGS_FILE: expected}
        assert measurement.tool_ignored_files == []
        assert measurement.environment is None
        assert measurement.tool is not None
        assert (measurement.tool.name, measurement.tool.version) == ("eslint", "10.12.0")

    def test_a_file_skipped_by_ignores_is_listed_and_not_counted(self, env: Env) -> None:
        env.report("eslint_context_forge.stdout", exit_code=0)
        files = [
            "packages/core/src/adoption/contracts.ts",
            "packages/core/src/adoption/adoptionState.ts",
            "packages/core/src/project-defaults.ts",
            IGNORED_FILE,
        ]

        measurement = env.measure(files)

        assert measurement.absent is None
        assert measurement.per_file == {}
        assert measurement.tool_ignored_files == [IGNORED_FILE]

    def test_a_real_warning_with_no_rule_id_is_still_counted(self, env: Env) -> None:
        """An unused-disable-directive warning has a null ruleId but a position."""
        report = [
            {
                "filePath": f"{env.repo}/a.ts",
                "messages": [
                    {
                        "ruleId": None,
                        "severity": 1,
                        "message": "Unused eslint-disable directive",
                        "line": 3,
                        "column": 1,
                    }
                ],
            }
        ]
        env.runner.script((str(env.eslint), "--format"), ToolResult(0, json.dumps(report), "", False))

        measurement = env.measure(["a.ts"])

        assert measurement.per_file == {"a.ts": 1}
        assert measurement.tool_ignored_files == []

    def test_eslint_runs_without_cache_over_the_explicit_files(self, env: Env) -> None:
        env.measure([FINDINGS_FILE])

        run = next(call for call in env.runner.calls if "--format" in call)
        assert run[1:] == ("--format", "json", FINDINGS_FILE)
        assert "--cache" not in run


class TestRuleSet:
    def test_config_is_hashed_by_content(self, env: Env) -> None:
        measurement = env.measure([FINDINGS_FILE])

        assert measurement.rule_set is not None
        assert measurement.rule_set.source == "eslint.config.mjs"
        assert measurement.rule_set.content_hash == hashlib.sha256(CONFIG_BYTES).hexdigest()

    def test_precedence_js_then_mjs_then_cjs(self, tmp_path: Path) -> None:
        for name in ("eslint.config.cjs", "eslint.config.mjs", "eslint.config.js"):
            (tmp_path / name).write_text("x", encoding="utf-8")
            rule_set = resolve_eslint_rule_set(tmp_path)
            assert rule_set is not None
            assert rule_set.source == name

    def test_no_config_resolves_to_none(self, tmp_path: Path) -> None:
        assert resolve_eslint_rule_set(tmp_path) is None


class TestFailureModes:
    def test_no_config_is_tool_failed_and_eslint_is_not_run(
        self, env: Env, caplog: pytest.LogCaptureFixture
    ) -> None:
        (env.repo / "eslint.config.mjs").unlink()

        measurement = env.measure([FINDINGS_FILE], caplog)

        assert_absent(
            measurement, AbsenceReason.TOOL_FAILED, "no eslint.config.{js,mjs,cjs} found", caplog
        )
        assert env.runner.calls == []

    def test_missing_binary(self, env: Env, caplog: pytest.LogCaptureFixture) -> None:
        env.eslint.unlink()

        measurement = env.measure([FINDINGS_FILE], caplog)

        assert_absent(
            measurement,
            AbsenceReason.TOOL_MISSING,
            "node_modules/.bin/eslint not found",
            caplog,
        )

    def test_a_global_eslint_on_path_is_never_used(
        self,
        env: Env,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        env.eslint.unlink()
        executable(tmp_path / "globalbin" / "eslint")
        monkeypatch.setenv("PATH", str(tmp_path / "globalbin"))

        measurement = env.measure([FINDINGS_FILE], caplog)

        assert_absent(measurement, AbsenceReason.TOOL_MISSING, "eslint not found", caplog)
        assert env.runner.calls == []

    def test_version_probe_failure_means_eslint_is_not_run(
        self, env: Env, caplog: pytest.LogCaptureFixture
    ) -> None:
        env.runner.script((str(env.eslint), "--version"), ToolResult(2, "", "boom", False))

        measurement = env.measure([FINDINGS_FILE], caplog)

        assert_absent(measurement, AbsenceReason.TOOL_FAILED, "version probe failed", caplog)
        assert not [c for c in env.runner.calls if "--format" in c]

    def test_timeout(self, env: Env, caplog: pytest.LogCaptureFixture) -> None:
        env.runner.script((str(env.eslint), "--format"), ToolResult(-1, "", "", True))

        assert_absent(
            env.measure([FINDINGS_FILE], caplog), AbsenceReason.TOOL_FAILED, "timed out", caplog
        )

    def test_bad_json(self, env: Env, caplog: pytest.LogCaptureFixture) -> None:
        env.runner.script((str(env.eslint), "--format"), ToolResult(0, "not json", "", False))

        assert_absent(
            env.measure([FINDINGS_FILE], caplog),
            AbsenceReason.TOOL_FAILED,
            "isn't valid JSON",
            caplog,
        )

    def test_fatal_config_load_exit(self, env: Env, caplog: pytest.LogCaptureFixture) -> None:
        stderr = read_fixture("eslint_fatal_config.stderr", env.repo)
        env.report("eslint_fatal_config.stdout", exit_code=2, stderr=stderr)

        assert_absent(
            env.measure([FINDINGS_FILE], caplog), AbsenceReason.TOOL_FAILED, "eslint exited 2", caplog
        )
