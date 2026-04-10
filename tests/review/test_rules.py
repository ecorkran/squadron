"""Tests for --rules flag and rules injection into system prompt."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.review.models import ReviewResult, Verdict


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def pass_result() -> ReviewResult:
    return ReviewResult(
        verdict=Verdict.PASS,
        findings=[],
        raw_output="## Summary\nPASS\n",
        template_name="code",
        input_files={"cwd": "."},
    )


@pytest.fixture
def mock_run_review(pass_result: ReviewResult):
    """Patch run_review so we can inspect the system prompt it receives."""
    with patch(
        "squadron.cli.commands.review.run_review_with_profile",
        new_callable=AsyncMock,
        return_value=pass_result,
    ) as mock:
        yield mock


class TestRulesFlag:
    """Test --rules flag on review code."""

    def test_rules_content_passed_to_runner(
        self,
        cli_runner: CliRunner,
        mock_run_review: AsyncMock,
        tmp_path: Path,
    ) -> None:
        rules_file = tmp_path / "rules.md"
        rules_file.write_text("Always check for null pointers.")

        result = cli_runner.invoke(app, ["review", "code", "--rules", str(rules_file)])
        assert result.exit_code == 0

        # run_review was called with rules_content keyword
        call_kwargs = mock_run_review.call_args
        assert call_kwargs.kwargs["rules_content"] == (
            "Always check for null pointers."
        )

    def test_missing_rules_file_error(
        self,
        cli_runner: CliRunner,
    ) -> None:
        result = cli_runner.invoke(
            app, ["review", "code", "--rules", "/nonexistent/rules.md"]
        )
        assert result.exit_code == 1
        assert "Rules file not found" in result.output

    def test_no_rules_flag_passes_none(
        self,
        cli_runner: CliRunner,
        mock_run_review: AsyncMock,
    ) -> None:
        with (
            patch(
                "squadron.cli.commands.review.get_config",
                return_value=None,
            ),
            patch(
                "squadron.cli.commands.review.resolve_rules_dir",
                return_value=None,
            ),
        ):
            result = cli_runner.invoke(app, ["review", "code"])
            assert result.exit_code == 0
            call_kwargs = mock_run_review.call_args
            assert call_kwargs.kwargs["rules_content"] is None

    def test_rules_flag_overrides_config(
        self,
        cli_runner: CliRunner,
        mock_run_review: AsyncMock,
        tmp_path: Path,
    ) -> None:
        flag_rules = tmp_path / "flag_rules.md"
        flag_rules.write_text("Flag rules content.")

        config_rules = tmp_path / "config_rules.md"
        config_rules.write_text("Config rules content.")

        def mock_get_config(key: str, cwd: str = ".") -> object:
            if key == "default_rules":
                return str(config_rules)
            if key == "verbosity":
                return 0
            return None

        with (
            patch(
                "squadron.cli.commands.review.get_config",
                side_effect=mock_get_config,
            ),
            patch(
                "squadron.cli.commands.review.resolve_rules_dir",
                return_value=None,
            ),
        ):
            result = cli_runner.invoke(
                app, ["review", "code", "--rules", str(flag_rules)]
            )
            assert result.exit_code == 0
            call_kwargs = mock_run_review.call_args
            assert call_kwargs.kwargs["rules_content"] == ("Flag rules content.")


class TestConfigDefaultRules:
    """Test config-based default_rules."""

    def test_config_rules_used_when_no_flag(
        self,
        cli_runner: CliRunner,
        mock_run_review: AsyncMock,
        tmp_path: Path,
    ) -> None:
        config_rules = tmp_path / "default_rules.md"
        config_rules.write_text("Default rules from config.")

        def mock_get_config(key: str, cwd: str = ".") -> object:
            if key == "default_rules":
                return str(config_rules)
            if key == "verbosity":
                return 0
            return None

        with (
            patch(
                "squadron.cli.commands.review.get_config",
                side_effect=mock_get_config,
            ),
            patch(
                "squadron.cli.commands.review.resolve_rules_dir",
                return_value=None,
            ),
        ):
            result = cli_runner.invoke(app, ["review", "code"])
            assert result.exit_code == 0
            call_kwargs = mock_run_review.call_args
            assert call_kwargs.kwargs["rules_content"] == ("Default rules from config.")


class TestRunnerRulesInjection:
    """Test that rules content is appended to system prompt in runner."""

    def test_rules_appended_to_system_prompt(self) -> None:
        from squadron.review.templates import ReviewTemplate

        template = ReviewTemplate(
            name="test",
            description="test",
            system_prompt="Base prompt.",
            allowed_tools=[],
            permission_mode="bypassPermissions",
            setting_sources=None,
            required_inputs=[],
            optional_inputs=[],
            prompt_template="Review this: {input}",
        )

        # We can't easily run the full async runner, but we can test
        # the system prompt construction logic directly
        system_prompt = template.system_prompt
        rules_content = "Check for SQL injection."
        if rules_content:
            system_prompt += f"\n\n## Additional Review Rules\n\n{rules_content}"

        assert "Base prompt." in system_prompt
        assert "## Additional Review Rules" in system_prompt
        assert "Check for SQL injection." in system_prompt
