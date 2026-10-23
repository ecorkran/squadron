"""Python adapter: ruff lint count (slice 400, D4, D8)."""

from __future__ import annotations

import logging
import stat
from pathlib import Path

import pytest

from squadron.metrology.snapshot.contract import ToolResult
from squadron.metrology.snapshot.python_lint import measure_ruff_lint, resolve_ruff_rule_set
from squadron.metrology.snapshot_models import (
    RULE_SET_SOURCE_TOOL_DEFAULTS,
    AbsenceReason,
    SnapshotMetric,
)
from tests.metrology.snapshot.builders import make_context, read_fixture
from tests.metrology.snapshot.conftest import FakeToolRunner


def install_ruff(repo: Path) -> Path:
    tool = repo / ".venv" / "bin" / "ruff"
    tool.parent.mkdir(parents=True)
    tool.write_text("#!/bin/sh\n", encoding="utf-8")
    tool.chmod(tool.stat().st_mode | stat.S_IXUSR)
    return tool


def scripted_runner(repo: Path, tool: Path, *, check: ToolResult | None = None) -> FakeToolRunner:
    version = ToolResult(0, read_fixture("version_ruff.stdout", repo), "", False)
    findings = ToolResult(0, read_fixture("ruff_scratch_findings.stdout", repo), "", False)
    return FakeToolRunner({(str(tool), "--version"): version, (str(tool), "check"): check or findings})


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("PATH", str(tmp_path / "no-tools-here"))
    root = tmp_path / "repo"
    root.mkdir()
    return root


def test_counts_match_the_real_ruff_fixture(repo: Path) -> None:
    tool = install_ruff(repo)
    runner = scripted_runner(repo, tool)

    measurement = measure_ruff_lint(make_context(repo, runner), ["bad.py"])

    assert measurement.absent is None
    assert measurement.metric is SnapshotMetric.LINT_COUNT
    assert measurement.per_file == {"bad.py": 3}
    assert measurement.tool is not None
    assert (measurement.tool.name, measurement.tool.version) == ("ruff", "0.15.1")
    assert measurement.rule_set is not None
    assert measurement.rule_set.source == RULE_SET_SOURCE_TOOL_DEFAULTS
    assert measurement.environment is None
    check = next(call for call in runner.calls if call[1] == "check")
    assert "--no-cache" in check and "--exit-zero" in check and check[-1] == "bad.py"


def test_a_clean_run_is_present_with_no_files_listed(repo: Path) -> None:
    tool = install_ruff(repo)
    clean = ToolResult(0, read_fixture("ruff_squadron_clean.stdout", repo), "", False)

    measurement = measure_ruff_lint(
        make_context(repo, scripted_runner(repo, tool, check=clean)), ["a.py"]
    )

    assert measurement.absent is None
    assert measurement.per_file == {}


def test_a_long_file_list_is_chunked_and_summed(repo: Path) -> None:
    tool = install_ruff(repo)
    runner = scripted_runner(repo, tool)
    files = [f"pkg/module_with_a_long_name_{n:05d}.py" for n in range(3000)]

    measurement = measure_ruff_lint(make_context(repo, runner), files)

    checks = [call for call in runner.calls if call[1] == "check"]
    assert len(checks) >= 2
    assert sorted(f for call in checks for f in call[6:]) == files
    assert measurement.per_file == {"bad.py": 3 * len(checks)}


class TestRuleSetSources:
    def test_ruff_toml_then_dot_ruff_toml_then_pyproject(self, repo: Path) -> None:
        (repo / "pyproject.toml").write_text("[tool.ruff]\nline-length = 100\n", encoding="utf-8")
        assert resolve_ruff_rule_set(repo).source == "pyproject.toml[tool.ruff]"

        (repo / ".ruff.toml").write_text("line-length = 90\n", encoding="utf-8")
        assert resolve_ruff_rule_set(repo).source == ".ruff.toml"

        (repo / "ruff.toml").write_text("line-length = 80\n", encoding="utf-8")
        assert resolve_ruff_rule_set(repo).source == "ruff.toml"

    def test_no_config_is_explicit_tool_defaults(self, repo: Path) -> None:
        rule_set = resolve_ruff_rule_set(repo)

        assert (rule_set.source, rule_set.content_hash) == (RULE_SET_SOURCE_TOOL_DEFAULTS, None)

    def test_pyproject_without_a_ruff_table_is_tool_defaults(self, repo: Path) -> None:
        (repo / "pyproject.toml").write_text('[project]\nname = "x"\n', encoding="utf-8")

        assert resolve_ruff_rule_set(repo).source == RULE_SET_SOURCE_TOOL_DEFAULTS

    def test_release_version_bump_does_not_change_the_hash_but_a_ruff_edit_does(
        self, repo: Path
    ) -> None:
        pyproject = repo / "pyproject.toml"
        pyproject.write_text('[project]\nversion = "1.0"\n[tool.ruff]\nline-length = 100\n')
        before = resolve_ruff_rule_set(repo).content_hash

        pyproject.write_text('[project]\nversion = "1.1"\n[tool.ruff]\nline-length = 100\n')
        assert resolve_ruff_rule_set(repo).content_hash == before

        pyproject.write_text('[project]\nversion = "1.1"\n[tool.ruff]\nline-length = 88\n')
        assert resolve_ruff_rule_set(repo).content_hash != before

    def test_key_order_in_the_table_does_not_change_the_hash(self, repo: Path) -> None:
        pyproject = repo / "pyproject.toml"
        pyproject.write_text("[tool.ruff]\nline-length = 100\ntarget-version = 'py312'\n")
        before = resolve_ruff_rule_set(repo).content_hash

        pyproject.write_text("[tool.ruff]\ntarget-version = 'py312'\nline-length = 100\n")

        assert resolve_ruff_rule_set(repo).content_hash == before


class TestFailureModes:
    def absent_with(self, repo: Path, runner: FakeToolRunner, caplog: pytest.LogCaptureFixture):
        with caplog.at_level(logging.WARNING):
            return measure_ruff_lint(make_context(repo, runner), ["a.py"])

    def test_missing_tool(self, repo: Path, caplog: pytest.LogCaptureFixture) -> None:
        measurement = self.absent_with(repo, FakeToolRunner(), caplog)

        assert measurement.absent is AbsenceReason.TOOL_MISSING
        assert "ruff not found" in (measurement.absent_detail or "")
        assert any(r.levelno == logging.WARNING for r in caplog.records)

    def test_version_probe_failure_means_ruff_is_not_run(
        self, repo: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        tool = install_ruff(repo)
        runner = FakeToolRunner({(str(tool), "--version"): ToolResult(2, "", "boom", False)})

        measurement = self.absent_with(repo, runner, caplog)

        assert measurement.absent is AbsenceReason.TOOL_FAILED
        assert "version probe failed" in (measurement.absent_detail or "")
        assert not [call for call in runner.calls if call[1] == "check"]
        assert any(r.levelno == logging.WARNING for r in caplog.records)

    @pytest.mark.parametrize(
        ("check", "expected_detail"),
        [
            (ToolResult(-1, "", "", True), "timed out"),
            (ToolResult(0, "not json", "", False), "isn't valid JSON"),
            (ToolResult(0, '{"a": 1}', "", False), "isn't a JSON list"),
            (ToolResult(2, "", "ruff: config error", False), "exited 2"),
        ],
    )
    def test_timeout_bad_output_and_bad_exit_are_tool_failed(
        self,
        repo: Path,
        caplog: pytest.LogCaptureFixture,
        check: ToolResult,
        expected_detail: str,
    ) -> None:
        tool = install_ruff(repo)

        measurement = self.absent_with(repo, scripted_runner(repo, tool, check=check), caplog)

        assert measurement.absent is AbsenceReason.TOOL_FAILED
        assert expected_detail in (measurement.absent_detail or "")
        assert measurement.per_file == {}
        assert any(r.levelno == logging.WARNING for r in caplog.records)

    def test_unparseable_pyproject_is_tool_failed(
        self, repo: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        tool = install_ruff(repo)
        (repo / "pyproject.toml").write_text("this is [not toml", encoding="utf-8")

        measurement = self.absent_with(repo, scripted_runner(repo, tool), caplog)

        assert measurement.absent is AbsenceReason.TOOL_FAILED
        assert "not valid TOML" in (measurement.absent_detail or "")
