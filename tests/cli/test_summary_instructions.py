"""Tests for the hidden ``sq _summary-instructions`` CLI command."""

from __future__ import annotations

from typer.testing import CliRunner

from squadron.cli.app import app

runner = CliRunner()


class TestSummaryInstructions:
    def test_not_listed_in_top_level_help(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "_summary-instructions" not in result.output

    def test_default_template_returns_rendered_text(self) -> None:
        """No args → uses configured or 'minimal' default."""
        result = runner.invoke(app, ["_summary-instructions"])
        assert result.exit_code == 0
        assert len(result.output.strip()) > 0

    def test_explicit_minimal_sdk_template(self) -> None:
        result = runner.invoke(app, ["_summary-instructions", "minimal-sdk"])
        assert result.exit_code == 0
        # minimal-sdk.yaml references third-person summary style
        assert len(result.output.strip()) > 0

    def test_missing_template_exits_with_error(self) -> None:
        result = runner.invoke(app, ["_summary-instructions", "nonexistent"])
        assert result.exit_code == 1
        assert "nonexistent" in result.output  # stderr captured in output by CliRunner

    def test_help_accessible(self) -> None:
        result = runner.invoke(app, ["_summary-instructions", "--help"])
        assert result.exit_code == 0
        assert "TEMPLATE" in result.output

    def test_suffix_flag_returns_suffix_for_minimal_sdk(self) -> None:
        result = runner.invoke(
            app, ["_summary-instructions", "minimal-sdk", "--suffix"]
        )
        assert result.exit_code == 0
        assert "Do not take any action" in result.output

    def test_suffix_flag_returns_empty_for_template_without_suffix(self) -> None:
        result = runner.invoke(app, ["_summary-instructions", "minimal", "--suffix"])
        assert result.exit_code == 0
        assert result.output.strip() == ""

    def test_suffix_flag_errors_on_missing_template(self) -> None:
        result = runner.invoke(
            app, ["_summary-instructions", "nonexistent", "--suffix"]
        )
        assert result.exit_code == 1
        assert "nonexistent" in result.output
