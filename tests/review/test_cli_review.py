"""Tests for the review CLI subcommand."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.review.models import (
    ReviewFinding,
    ReviewResult,
    Severity,
    Verdict,
)


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_review_result() -> ReviewResult:
    return ReviewResult(
        verdict=Verdict.CONCERNS,
        findings=[
            ReviewFinding(
                severity=Severity.CONCERN,
                title="Missing validation",
                description="Input not validated.",
            ),
            ReviewFinding(
                severity=Severity.PASS,
                title="Clean structure",
                description="Good layout.",
            ),
        ],
        raw_output="## Summary\nCONCERNS\n...",
        template_name="arch",
        input_files={"input": "a.md", "against": "b.md"},
    )


@pytest.fixture
def patch_run_review(mock_review_result: ReviewResult):  # type: ignore[no-untyped-def]
    """Patch run_review to return mock result without SDK calls."""
    with patch(
        "squadron.cli.commands.review.run_review_with_profile",
        new_callable=AsyncMock,
        return_value=mock_review_result,
    ) as mock:
        yield mock


class TestReviewSlice:
    """Test review slice command."""

    def test_with_required_args(
        self,
        cli_runner: CliRunner,
        patch_run_review: AsyncMock,
    ) -> None:
        result = cli_runner.invoke(
            app, ["review", "slice", "slice.md", "--against", "arch.md"]
        )
        assert result.exit_code == 0
        assert "CONCERNS" in result.output

    def test_missing_against_arg(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(app, ["review", "slice", "slice.md"])
        assert result.exit_code != 0


class TestReviewTasks:
    """Test review tasks command."""

    def test_with_required_args(
        self,
        cli_runner: CliRunner,
        patch_run_review: AsyncMock,
    ) -> None:
        # Update mock to return tasks template name
        patch_run_review.return_value = ReviewResult(
            verdict=Verdict.PASS,
            findings=[],
            raw_output="## Summary\nPASS\n",
            template_name="tasks",
            input_files={"input": "t.md", "against": "s.md"},
        )
        result = cli_runner.invoke(
            app, ["review", "tasks", "tasks.md", "--against", "slice.md"]
        )
        assert result.exit_code == 0

    def test_missing_against_arg(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(app, ["review", "tasks", "tasks.md"])
        assert result.exit_code != 0


class TestReviewCode:
    """Test review code command."""

    def test_with_no_args(
        self,
        cli_runner: CliRunner,
        patch_run_review: AsyncMock,
    ) -> None:
        patch_run_review.return_value = ReviewResult(
            verdict=Verdict.PASS,
            findings=[],
            raw_output="## Summary\nPASS\n",
            template_name="code",
            input_files={"cwd": "."},
        )
        result = cli_runner.invoke(app, ["review", "code"])
        assert result.exit_code == 0

    def test_with_files_flag(
        self,
        cli_runner: CliRunner,
        patch_run_review: AsyncMock,
    ) -> None:
        patch_run_review.return_value = ReviewResult(
            verdict=Verdict.PASS,
            findings=[],
            raw_output="## Summary\nPASS\n",
            template_name="code",
            input_files={"cwd": ".", "files": "src/**/*.py"},
        )
        result = cli_runner.invoke(app, ["review", "code", "--files", "src/**/*.py"])
        assert result.exit_code == 0

    def test_with_diff_flag(
        self,
        cli_runner: CliRunner,
        patch_run_review: AsyncMock,
    ) -> None:
        patch_run_review.return_value = ReviewResult(
            verdict=Verdict.PASS,
            findings=[],
            raw_output="## Summary\nPASS\n",
            template_name="code",
            input_files={"cwd": ".", "diff": "main"},
        )
        result = cli_runner.invoke(app, ["review", "code", "--diff", "main"])
        assert result.exit_code == 0


class TestReviewList:
    """Test review list command."""

    def test_lists_all_templates(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(app, ["review", "list"])
        assert result.exit_code == 0
        assert "slice" in result.output
        assert "tasks" in result.output
        assert "code" in result.output


class TestOutputModes:
    """Test --output modes."""

    def test_json_output(
        self,
        cli_runner: CliRunner,
        patch_run_review: AsyncMock,
    ) -> None:
        result = cli_runner.invoke(
            app,
            ["review", "slice", "a.md", "--against", "b.md", "--output", "json"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["verdict"] == "CONCERNS"
        assert len(data["findings"]) == 2
        assert "template_name" in data

    def test_file_output(
        self,
        cli_runner: CliRunner,
        patch_run_review: AsyncMock,
        tmp_path: Path,
    ) -> None:
        out_file = tmp_path / "result.json"
        result = cli_runner.invoke(
            app,
            [
                "review",
                "arch",
                "a.md",
                "--against",
                "b.md",
                "--output",
                "file",
                "--output-path",
                str(out_file),
            ],
        )
        assert result.exit_code == 0
        assert out_file.exists()
        data = json.loads(out_file.read_text())
        assert data["verdict"] == "CONCERNS"


class TestErrorCases:
    """Test error handling in review commands."""

    def test_fail_verdict_exits_with_code_2(
        self,
        cli_runner: CliRunner,
        patch_run_review: AsyncMock,
    ) -> None:
        patch_run_review.return_value = ReviewResult(
            verdict=Verdict.FAIL,
            findings=[
                ReviewFinding(
                    severity=Severity.FAIL,
                    title="Critical",
                    description="Bad.",
                ),
            ],
            raw_output="## Summary\nFAIL\n",
            template_name="arch",
            input_files={"input": "a.md", "against": "b.md"},
        )
        result = cli_runner.invoke(
            app, ["review", "slice", "a.md", "--against", "b.md"]
        )
        assert result.exit_code == 2
