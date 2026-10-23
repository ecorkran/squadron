"""Runner, tool resolution and version-probe tests (slice 400, D8)."""

from __future__ import annotations

import logging
import stat
import sys
from pathlib import Path

import pytest

from squadron.metrology.snapshot.contract import ToolResult
from squadron.metrology.snapshot.runner import (
    SubprocessToolRunner,
    chunk_files,
    probe_version,
    resolve_tool,
)
from tests.metrology.snapshot.conftest import FakeToolRunner

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "snapshot"


def ok(stdout: str = "", stderr: str = "", exit_code: int = 0) -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, timed_out=False)


def make_executable(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


class TestSubprocessToolRunner:
    def test_command_over_the_timeout_returns_timed_out(self, tmp_path: Path) -> None:
        result = SubprocessToolRunner().run(
            [sys.executable, "-c", "import time; time.sleep(30)"], cwd=tmp_path, timeout_s=1
        )

        assert result.timed_out is True
        assert result.exit_code < 0

    def test_captures_output_and_exit_code_without_a_shell(self, tmp_path: Path) -> None:
        result = SubprocessToolRunner().run(
            [sys.executable, "-c", "import sys; print('a b;c'); sys.exit(3)"],
            cwd=tmp_path,
            timeout_s=30,
        )

        assert (result.exit_code, result.stdout.strip(), result.timed_out) == (3, "a b;c", False)

    def test_missing_binary_is_a_failed_call_not_an_exception(self, tmp_path: Path) -> None:
        result = SubprocessToolRunner().run([str(tmp_path / "no-such-tool")], cwd=tmp_path, timeout_s=5)

        assert result.timed_out is False
        assert result.exit_code < 0
        assert "no-such-tool" in result.stderr


class TestResolveTool:
    def test_project_binary_wins_over_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project_tool = make_executable(tmp_path / "repo" / ".venv" / "bin" / "ruff")
        path_dir = tmp_path / "pathdir"
        make_executable(path_dir / "ruff")
        monkeypatch.setenv("PATH", str(path_dir))

        found = resolve_tool(tmp_path / "repo", "ruff", [".venv/bin"], use_path=True)

        assert found == project_tool

    def test_path_is_used_when_allowed_and_the_project_has_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path_tool = make_executable(tmp_path / "pathdir" / "ruff")
        monkeypatch.setenv("PATH", str(tmp_path / "pathdir"))

        found = resolve_tool(tmp_path / "repo", "ruff", [".venv/bin"], use_path=True)

        assert found == path_tool

    def test_eslint_is_never_resolved_from_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        make_executable(tmp_path / "pathdir" / "eslint")
        monkeypatch.setenv("PATH", str(tmp_path / "pathdir"))

        assert resolve_tool(tmp_path / "repo", "eslint", ["node_modules/.bin"], use_path=False) is None

    def test_missing_tool_returns_none(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PATH", str(tmp_path / "empty"))

        assert resolve_tool(tmp_path, "pyright", [".venv/bin"], use_path=True) is None

    def test_non_executable_file_is_not_a_tool(self, tmp_path: Path) -> None:
        candidate = tmp_path / ".venv" / "bin" / "ruff"
        candidate.parent.mkdir(parents=True)
        candidate.write_text("x", encoding="utf-8")
        candidate.chmod(stat.S_IRUSR | stat.S_IWUSR)

        assert resolve_tool(tmp_path, "ruff", [".venv/bin"], use_path=False) is None


class TestProbeVersion:
    @pytest.mark.parametrize(
        ("capture", "expected"),
        [
            ("version_ruff", "0.15.1"),
            ("version_pyright", "1.1.408"),
            ("version_uv", "0.11.2"),
            ("version_eslint", "10.12.0"),
        ],
    )
    def test_parses_each_real_version_capture(
        self, tmp_path: Path, capture: str, expected: str
    ) -> None:
        stdout = (FIXTURES / f"{capture}.stdout").read_text(encoding="utf-8")
        runner = FakeToolRunner({("/bin/tool",): ok(stdout)})

        probe = probe_version(runner, Path("/bin/tool"), tmp_path, timeout_s=5)

        assert (probe.version, probe.failure) == (expected, None)

    @pytest.mark.parametrize(
        ("result", "reason"),
        [
            (ToolResult(exit_code=-1, stdout="", stderr="", timed_out=True), "timed out"),
            (ok("", "boom", exit_code=2), "exit 2"),
            (ok("no digits here"), "no version in output"),
        ],
    )
    def test_failures_return_detail_and_log_a_warning(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
        result: ToolResult,
        reason: str,
    ) -> None:
        runner = FakeToolRunner({("/bin/tool",): result})

        with caplog.at_level(logging.WARNING):
            probe = probe_version(runner, Path("/bin/tool"), tmp_path, timeout_s=5)

        assert probe.version is None
        assert probe.failure is not None
        assert probe.failure.startswith("version probe failed: ")
        assert reason in probe.failure
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1
        assert "/bin/tool --version" in warnings[0].getMessage()


class TestChunking:
    def test_every_file_lands_in_exactly_one_chunk_in_order(self) -> None:
        files = [f"dir/file_{n:04d}.py" for n in range(500)]

        chunks = list(chunk_files(files, budget=1000))

        assert len(chunks) > 1
        assert [f for chunk in chunks for f in chunk] == files
        assert all(sum(len(f) + 1 for f in chunk) <= 1000 for chunk in chunks)

    def test_an_oversized_path_gets_its_own_chunk(self) -> None:
        chunks = list(chunk_files(["a.py", "x" * 50, "b.py"], budget=20))

        assert chunks == [["a.py"], ["x" * 50], ["b.py"]]

    def test_no_files_yields_no_chunks(self) -> None:
        assert list(chunk_files([])) == []
