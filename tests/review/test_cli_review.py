"""Tests for the review CLI subcommand."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.integrations.context_forge import (
    ContextForgeError,
    ContextForgeNotAvailable,
)
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
                "slice",
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


class TestRulesWiring:
    """T13: Tests for language rules auto-detection and template rules wiring."""

    def test_review_code_no_rules_flag_suppresses_injection(
        self,
        cli_runner: CliRunner,
        patch_run_review: AsyncMock,
        tmp_path: Path,
    ) -> None:
        """--no-rules suppresses all rule injection."""
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        (rules_dir / "python.md").write_text("Python rules content.")

        with patch("squadron.cli.commands.review.get_config", return_value=None):
            result = cli_runner.invoke(
                app,
                [
                    "review",
                    "code",
                    "--no-rules",
                    "--rules-dir",
                    str(rules_dir),
                    "--diff",
                    "main",
                ],
            )
        assert result.exit_code == 0
        call_kwargs = patch_run_review.call_args.kwargs
        assert call_kwargs["rules_content"] is None

    def test_review_slice_template_rules_injected(
        self,
        cli_runner: CliRunner,
        patch_run_review: AsyncMock,
        tmp_path: Path,
    ) -> None:
        """rules/review-slice.md present → injected into slice review."""
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        (rules_dir / "review-slice.md").write_text("Slice-specific review guidance.")

        result = cli_runner.invoke(
            app,
            [
                "review",
                "slice",
                "slice.md",
                "--against",
                "arch.md",
                "--rules-dir",
                str(rules_dir),
            ],
        )
        assert result.exit_code == 0
        call_kwargs = patch_run_review.call_args.kwargs
        assert call_kwargs["rules_content"] is not None
        assert "Slice-specific review guidance." in call_kwargs["rules_content"]

    def test_review_code_explicit_and_auto_combined(
        self,
        cli_runner: CliRunner,
        patch_run_review: AsyncMock,
        tmp_path: Path,
    ) -> None:
        """--rules custom.md + auto-detected rules both present in rules_content."""
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        (rules_dir / "python.md").write_text(
            "---\npaths: [**/*.py]\n---\nPython auto rules."
        )
        explicit_rules = tmp_path / "custom.md"
        explicit_rules.write_text("Explicit custom rules.")

        # Patch git diff to return a .py file
        with patch(
            "squadron.cli.commands.review._extract_diff_paths",
            return_value=["src/foo.py"],
        ):
            result = cli_runner.invoke(
                app,
                [
                    "review",
                    "code",
                    "--rules",
                    str(explicit_rules),
                    "--rules-dir",
                    str(rules_dir),
                    "--diff",
                    "main",
                ],
            )
        assert result.exit_code == 0
        call_kwargs = patch_run_review.call_args.kwargs
        rc = call_kwargs["rules_content"]
        assert rc is not None
        assert "Explicit custom rules." in rc
        assert "Python auto rules." in rc


class TestContextForgeErrors:
    """Test error handling when CF is unavailable or fails."""

    def test_review_slice_cf_not_available(self, cli_runner: CliRunner) -> None:
        with patch("squadron.cli.commands.review.ContextForgeClient") as mock_cls:
            mock_cls.return_value.list_slices.side_effect = ContextForgeNotAvailable(
                "cf not found"
            )
            result = cli_runner.invoke(app, ["review", "slice", "122"])
            assert result.exit_code == 1
            assert "not installed" in result.output

    def test_review_slice_cf_error(self, cli_runner: CliRunner) -> None:
        with patch("squadron.cli.commands.review.ContextForgeClient") as mock_cls:
            mock_cls.return_value.list_slices.side_effect = ContextForgeError(
                "connection refused"
            )
            result = cli_runner.invoke(app, ["review", "slice", "122"])
            assert result.exit_code == 1
            assert "connection refused" in result.output

    def test_review_tasks_cf_not_available(self, cli_runner: CliRunner) -> None:
        with patch("squadron.cli.commands.review.ContextForgeClient") as mock_cls:
            mock_cls.return_value.list_slices.side_effect = ContextForgeNotAvailable(
                "cf not found"
            )
            result = cli_runner.invoke(app, ["review", "tasks", "122"])
            assert result.exit_code == 1
            assert "not installed" in result.output


class TestScopedDiff:
    """T12: Tests for scoped diff resolution in review_code()."""

    def test_slice_number_calls_resolve_diff(
        self,
        cli_runner: CliRunner,
        patch_run_review: AsyncMock,
    ) -> None:
        """review code 122 → resolve_slice_diff_range called."""
        mock_slice_info = {
            "index": 122,
            "name": "test",
            "slice_name": "test",
            "design_file": "slice.md",
            "task_files": [],
            "arch_file": "arch.md",
        }
        with (
            patch(
                "squadron.cli.commands.review._resolve_slice_number",
                return_value=mock_slice_info,
            ),
            patch(
                "squadron.cli.commands.review.resolve_slice_diff_range",
                return_value="abc123...122-slice.foo",
            ) as mock_resolve,
        ):
            result = cli_runner.invoke(app, ["review", "code", "122", "--no-save"])
        assert result.exit_code == 0
        mock_resolve.assert_called_once()
        assert mock_resolve.call_args[0][0] == 122

    def test_explicit_diff_overrides_resolution(
        self,
        cli_runner: CliRunner,
        patch_run_review: AsyncMock,
    ) -> None:
        """review code 122 --diff HEAD~3 → explicit diff used, no resolution."""
        mock_slice_info = {
            "index": 122,
            "name": "test",
            "slice_name": "test",
            "design_file": "slice.md",
            "task_files": [],
            "arch_file": "arch.md",
        }
        with (
            patch(
                "squadron.cli.commands.review._resolve_slice_number",
                return_value=mock_slice_info,
            ),
            patch(
                "squadron.cli.commands.review.resolve_slice_diff_range",
            ) as mock_resolve,
        ):
            result = cli_runner.invoke(
                app, ["review", "code", "122", "--diff", "HEAD~3", "--no-save"]
            )
        assert result.exit_code == 0
        mock_resolve.assert_not_called()
        # Verify the diff passed to review is HEAD~3
        call_kwargs = patch_run_review.call_args
        inputs = call_kwargs[0][1] if call_kwargs[0] else call_kwargs[1].get("inputs")
        if inputs is None:
            inputs = call_kwargs[0][1]
        assert inputs.get("diff") == "HEAD~3"

    def test_no_slice_number_no_resolution(
        self,
        cli_runner: CliRunner,
        patch_run_review: AsyncMock,
    ) -> None:
        """review code (no slice number) → resolve not called."""
        patch_run_review.return_value = ReviewResult(
            verdict=Verdict.PASS,
            findings=[],
            raw_output="## Summary\nPASS\n",
            template_name="code",
            input_files={"cwd": "."},
        )
        with patch(
            "squadron.cli.commands.review.resolve_slice_diff_range",
        ) as mock_resolve:
            result = cli_runner.invoke(app, ["review", "code"])
        assert result.exit_code == 0
        mock_resolve.assert_not_called()
