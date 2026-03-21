"""Tests for verbosity levels and text color in review display."""

from __future__ import annotations

from io import StringIO
from unittest.mock import AsyncMock, patch

import pytest
from rich.console import Console
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.cli.commands.review import (
    _display_terminal,  # pyright: ignore[reportPrivateUsage]
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
def sample_result() -> ReviewResult:
    return ReviewResult(
        verdict=Verdict.CONCERNS,
        findings=[
            ReviewFinding(
                severity=Severity.CONCERN,
                title="Missing validation",
                description="Input not validated at boundary.",
            ),
            ReviewFinding(
                severity=Severity.PASS,
                title="Clean structure",
                description="Good module layout.",
                file_ref="src/module.py:10",
            ),
        ],
        raw_output="## Summary\nCONCERNS\n\n## Findings\n\nFull raw text here.",
        template_name="arch",
        input_files={"input": "a.md", "against": "b.md"},
    )


def _capture_terminal(result: ReviewResult, verbosity: int) -> str:
    """Capture _display_terminal output as plain text."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=120)
    with patch("squadron.cli.commands.review.Console", return_value=console):
        _display_terminal(result, verbosity)
    return buf.getvalue()


class TestModelInHeader:
    """Test model shown in panel header."""

    def test_model_shown_when_set(self) -> None:
        result = ReviewResult(
            verdict=Verdict.PASS,
            findings=[],
            raw_output="",
            template_name="arch",
            input_files={},
            model="opus",
        )
        output = _capture_terminal(result, 0)
        assert "opus" in output

    def test_model_omitted_when_none(self, sample_result: ReviewResult) -> None:
        output = _capture_terminal(sample_result, 0)
        assert "Model:" not in output


class TestVerbosity0:
    """Verbosity 0: verdict + headings only, no descriptions."""

    def test_shows_verdict(self, sample_result: ReviewResult) -> None:
        output = _capture_terminal(sample_result, 0)
        assert "CONCERNS" in output

    def test_shows_finding_headings(self, sample_result: ReviewResult) -> None:
        output = _capture_terminal(sample_result, 0)
        assert "Missing validation" in output
        assert "Clean structure" in output

    def test_hides_descriptions(self, sample_result: ReviewResult) -> None:
        output = _capture_terminal(sample_result, 0)
        assert "Input not validated" not in output
        assert "Good module layout" not in output

    def test_hides_file_refs(self, sample_result: ReviewResult) -> None:
        output = _capture_terminal(sample_result, 0)
        assert "src/module.py" not in output


class TestVerbosity1:
    """Verbosity 1: verdict + headings + descriptions."""

    def test_shows_descriptions(self, sample_result: ReviewResult) -> None:
        output = _capture_terminal(sample_result, 1)
        assert "Input not validated" in output
        assert "Good module layout" in output

    def test_shows_file_refs(self, sample_result: ReviewResult) -> None:
        output = _capture_terminal(sample_result, 1)
        assert "src/module.py" in output

    def test_hides_raw_output(self, sample_result: ReviewResult) -> None:
        output = _capture_terminal(sample_result, 1)
        assert "Full raw text here" not in output


class TestVerbosity2:
    """Verbosity 2: same as level 1 (raw output not displayed)."""

    def test_no_raw_output(self, sample_result: ReviewResult) -> None:
        output = _capture_terminal(sample_result, 2)
        assert "Full raw text here" not in output

    def test_shows_descriptions(self, sample_result: ReviewResult) -> None:
        output = _capture_terminal(sample_result, 2)
        assert "Input not validated" in output


class TestVerboseFlag:
    """Test -v flag on CLI commands."""

    @pytest.fixture
    def mock_review(self, sample_result: ReviewResult):
        with patch(
            "squadron.cli.commands.review.run_review",
            new_callable=AsyncMock,
            return_value=sample_result,
        ) as mock:
            yield mock

    def test_v_flag_sets_verbosity_1(
        self,
        cli_runner: CliRunner,
        mock_review: AsyncMock,
    ) -> None:
        result = cli_runner.invoke(
            app, ["review", "arch", "a.md", "--against", "b.md", "-v"]
        )
        assert result.exit_code == 0
        assert "Input not validated" in result.output

    def test_no_flag_uses_verbosity_0(
        self,
        cli_runner: CliRunner,
        mock_review: AsyncMock,
    ) -> None:
        with patch(
            "squadron.cli.commands.review.get_config",
            return_value=0,
        ):
            result = cli_runner.invoke(
                app, ["review", "arch", "a.md", "--against", "b.md"]
            )
            assert result.exit_code == 0
            assert "Input not validated" not in result.output


class TestConfigDefaultVerbosity:
    """Test config-based default verbosity."""

    @pytest.fixture
    def mock_review(self, sample_result: ReviewResult):
        with patch(
            "squadron.cli.commands.review.run_review",
            new_callable=AsyncMock,
            return_value=sample_result,
        ) as mock:
            yield mock

    def test_config_verbosity_1_shows_descriptions(
        self,
        cli_runner: CliRunner,
        mock_review: AsyncMock,
    ) -> None:
        with patch(
            "squadron.cli.commands.review.get_config",
            return_value=1,
        ):
            result = cli_runner.invoke(
                app, ["review", "arch", "a.md", "--against", "b.md"]
            )
            assert result.exit_code == 0
            assert "Input not validated" in result.output
