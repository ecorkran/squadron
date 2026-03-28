"""Tests for model resolution precedence in review CLI."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.cli.commands.review import (
    _resolve_model,  # pyright: ignore[reportPrivateUsage]
)
from squadron.review.models import ReviewResult, Verdict
from squadron.review.templates import ReviewTemplate


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_run_review() -> AsyncMock:
    """Patch run_review to return a minimal result."""
    result = ReviewResult(
        verdict=Verdict.PASS,
        findings=[],
        raw_output="## Summary\nPASS\n",
        template_name="arch",
        input_files={"input": "a.md", "against": "b.md"},
        model="opus",
    )
    with patch(
        "squadron.cli.commands.review.run_review_with_profile",
        new_callable=AsyncMock,
        return_value=result,
    ) as mock:
        yield mock


def _make_template(model: str | None = None) -> ReviewTemplate:
    return ReviewTemplate(
        name="test",
        description="Test",
        system_prompt="Review.",
        allowed_tools=["Read"],
        permission_mode="bypassPermissions",
        setting_sources=None,
        required_inputs=[],
        optional_inputs=[],
        model=model,
        prompt_template="Review all.",
    )


class TestResolveModel:
    """Test _resolve_model precedence: flag → config → template → None."""

    def test_flag_wins_over_all(self) -> None:
        template = _make_template(model="sonnet")
        with patch("squadron.cli.commands.review.get_config", return_value="haiku"):
            assert _resolve_model("opus", template) == "opus"

    def test_config_wins_over_template(self) -> None:
        template = _make_template(model="sonnet")
        with patch("squadron.cli.commands.review.get_config", return_value="haiku"):
            assert _resolve_model(None, template) == "haiku"

    def test_template_wins_over_none(self) -> None:
        template = _make_template(model="sonnet")
        with patch("squadron.cli.commands.review.get_config", return_value=None):
            assert _resolve_model(None, template) == "sonnet"

    def test_all_absent_returns_none(self) -> None:
        template = _make_template(model=None)
        with patch("squadron.cli.commands.review.get_config", return_value=None):
            assert _resolve_model(None, template) is None

    def test_no_template_falls_through(self) -> None:
        with patch("squadron.cli.commands.review.get_config", return_value=None):
            assert _resolve_model(None) is None


class TestModelCLIFlag:
    """Test --model flag passes through to run_review."""

    def test_arch_model_flag(
        self,
        cli_runner: CliRunner,
        mock_run_review: AsyncMock,
    ) -> None:
        result = cli_runner.invoke(
            app,
            ["review", "arch", "a.md", "--model", "sonnet", "--no-save"],
        )
        assert result.exit_code == 0
        call_kwargs = mock_run_review.call_args.kwargs
        # Alias "sonnet" resolves to full model ID
        assert call_kwargs["model"] == "claude-sonnet-4-6"

    def test_tasks_model_flag(
        self,
        cli_runner: CliRunner,
        mock_run_review: AsyncMock,
    ) -> None:
        mock_run_review.return_value = ReviewResult(
            verdict=Verdict.PASS,
            findings=[],
            raw_output="## Summary\nPASS\n",
            template_name="tasks",
            input_files={"input": "t.md", "against": "s.md"},
            model="claude-opus-4-6",
        )
        result = cli_runner.invoke(
            app,
            ["review", "tasks", "t.md", "--against", "s.md", "--model", "opus"],
        )
        assert result.exit_code == 0
        call_kwargs = mock_run_review.call_args.kwargs
        # Alias "opus" resolves to full model ID
        assert call_kwargs["model"] == "claude-opus-4-6"

    def test_code_model_flag(
        self,
        cli_runner: CliRunner,
        mock_run_review: AsyncMock,
    ) -> None:
        mock_run_review.return_value = ReviewResult(
            verdict=Verdict.PASS,
            findings=[],
            raw_output="## Summary\nPASS\n",
            template_name="code",
            input_files={"cwd": "."},
            model="claude-haiku-4-5-20251001",
        )
        result = cli_runner.invoke(
            app,
            ["review", "code", "--model", "haiku"],
        )
        assert result.exit_code == 0
        call_kwargs = mock_run_review.call_args.kwargs
        # Alias "haiku" resolves to full model ID
        assert call_kwargs["model"] == "claude-haiku-4-5-20251001"

    def test_config_default_model_resolves_alias(
        self,
        cli_runner: CliRunner,
        mock_run_review: AsyncMock,
    ) -> None:
        """Config default_model must go through alias resolution (bug fix)."""
        with patch(
            "squadron.cli.commands.review.get_config",
            side_effect=lambda key: "minimax" if key == "default_model" else None,
        ):
            result = cli_runner.invoke(
                app,
                ["review", "slice", "a.md", "--against", "b.md"],
            )
        assert result.exit_code == 0
        call_kwargs = mock_run_review.call_args.kwargs
        # "minimax" alias should resolve to full model ID, not bare "minimax"
        assert call_kwargs["model"] == "minimax/minimax-m2.7"
        # Profile should be inferred from alias
        assert call_kwargs["profile"] == "openrouter"
