"""Tests for the bash tool."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from squadron.tools import builtin, limits, registry  # noqa: F401  # builtin registers on import
from squadron.tools.models import ToolExecutor


@pytest.fixture
def bash(tmp_path: Path) -> ToolExecutor:
    return registry.materialize(["bash"], tmp_path)["bash"]


async def test_stdout_is_captured_and_labeled(bash: ToolExecutor) -> None:
    result = await bash({"command": "echo hello-stdout"})

    assert result.is_error is False
    assert "stdout:" in result.content
    assert "hello-stdout" in result.content


async def test_stderr_is_captured_and_labeled(bash: ToolExecutor) -> None:
    result = await bash({"command": "echo hello-stderr >&2"})

    assert result.is_error is False
    assert "stderr:" in result.content
    assert "hello-stderr" in result.content


async def test_command_runs_in_the_working_directory(tmp_path: Path, bash: ToolExecutor) -> None:
    (tmp_path / "marker-file.txt").write_text("x")

    result = await bash({"command": "ls"})

    assert result.is_error is False
    assert "marker-file.txt" in result.content


async def test_non_zero_exit_reports_code_and_keeps_output(bash: ToolExecutor) -> None:
    result = await bash({"command": "echo before-failure; exit 3"})

    assert result.is_error is True
    assert "code 3" in result.content
    assert "before-failure" in result.content


async def test_oversized_output_is_truncated_with_a_visible_marker(
    bash: ToolExecutor, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(limits, "MAX_OUTPUT_BYTES", 20)

    result = await bash({"command": "printf 'x%.0s' $(seq 1 500)"})

    assert result.is_error is False
    assert "truncated" in result.content
    assert "500 bytes" in result.content


async def test_timeout_kills_the_command_and_reports(
    bash: ToolExecutor, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(limits, "BASH_TIMEOUT_S", 0.2)

    result = await bash({"command": "sleep 30"})

    assert result.is_error is True
    assert "timed out" in result.content
    assert "0.2" in result.content


async def test_timeout_logs_at_warning(
    bash: ToolExecutor, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(limits, "BASH_TIMEOUT_S", 0.2)

    with caplog.at_level(logging.WARNING, logger="squadron.tools.builtin"):
        await bash({"command": "sleep 30"})

    records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert records
    assert "timed out" in records[0].getMessage()


async def test_non_zero_exit_logs_at_info(bash: ToolExecutor, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="squadron.tools.builtin")

    await bash({"command": "exit 3"})

    records = [r for r in caplog.records if r.levelno == logging.INFO]
    assert records
    assert "code 3" in records[0].getMessage()
