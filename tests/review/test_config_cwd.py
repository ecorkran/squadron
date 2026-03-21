"""Tests for config-based --cwd resolution in review commands."""

from __future__ import annotations

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
    with patch(
        "squadron.cli.commands.review.run_review_with_profile",
        new_callable=AsyncMock,
        return_value=pass_result,
    ) as mock:
        yield mock


class TestConfigCwd:
    """Test config-based cwd resolution."""

    def test_config_cwd_used_when_no_flag(
        self,
        cli_runner: CliRunner,
        mock_run_review: AsyncMock,
    ) -> None:
        def mock_get_config(key: str, cwd: str = ".") -> object:
            if key == "cwd":
                return "/configured/path"
            if key == "verbosity":
                return 0
            return None

        with patch(
            "squadron.cli.commands.review.get_config",
            side_effect=mock_get_config,
        ):
            result = cli_runner.invoke(app, ["review", "code"])
            assert result.exit_code == 0
            # Verify run_review was called with the config cwd
            call_args = mock_run_review.call_args
            _, inputs = call_args.args
            assert inputs["cwd"] == "/configured/path"

    def test_flag_overrides_config_cwd(
        self,
        cli_runner: CliRunner,
        mock_run_review: AsyncMock,
    ) -> None:
        def mock_get_config(key: str, cwd: str = ".") -> object:
            if key == "cwd":
                return "/configured/path"
            if key == "verbosity":
                return 0
            return None

        with patch(
            "squadron.cli.commands.review.get_config",
            side_effect=mock_get_config,
        ):
            result = cli_runner.invoke(
                app, ["review", "code", "--cwd", "/explicit/path"]
            )
            assert result.exit_code == 0
            call_args = mock_run_review.call_args
            _, inputs = call_args.args
            assert inputs["cwd"] == "/explicit/path"

    def test_default_dot_when_no_config_no_flag(
        self,
        cli_runner: CliRunner,
        mock_run_review: AsyncMock,
    ) -> None:
        def mock_get_config(key: str, cwd: str = ".") -> object:
            if key == "cwd":
                return "."
            if key == "verbosity":
                return 0
            return None

        with patch(
            "squadron.cli.commands.review.get_config",
            side_effect=mock_get_config,
        ):
            result = cli_runner.invoke(app, ["review", "code"])
            assert result.exit_code == 0
            call_args = mock_run_review.call_args
            _, inputs = call_args.args
            assert inputs["cwd"] == "."
