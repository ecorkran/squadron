"""Tests for _resolve_profile() and _infer_profile_from_model()."""

from __future__ import annotations

import pytest

# Import the private helpers under test
from squadron.cli.commands.review import (
    _infer_profile_from_model,
    _resolve_profile,
)
from squadron.review.templates import ReviewTemplate


def _make_template(
    profile: str | None = None, model: str | None = None
) -> ReviewTemplate:
    """Create a minimal ReviewTemplate for testing."""
    return ReviewTemplate(
        name="test",
        description="Test template",
        system_prompt="You are a reviewer.",
        allowed_tools=[],
        permission_mode="bypassPermissions",
        setting_sources=None,
        required_inputs=[],
        optional_inputs=[],
        prompt_template="review {input}",
        profile=profile,
        model=model,
    )


class TestResolveProfile:
    """Test _resolve_profile() resolution chain."""

    def test_cli_flag_takes_precedence(self, monkeypatch: pytest.MonkeyPatch) -> None:
        template = _make_template(profile="openrouter")
        monkeypatch.setattr(
            "squadron.cli.commands.review.get_config",
            lambda k: "local" if k == "default_review_profile" else None,
        )
        result = _resolve_profile("openai", template)
        assert result == "openai"

    def test_template_profile_takes_precedence_over_config(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        template = _make_template(profile="openrouter")
        monkeypatch.setattr(
            "squadron.cli.commands.review.get_config",
            lambda k: "local" if k == "default_review_profile" else None,
        )
        result = _resolve_profile(None, template)
        assert result == "openrouter"

    def test_config_used_when_no_flag_or_template(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        template = _make_template(profile=None)
        monkeypatch.setattr(
            "squadron.cli.commands.review.get_config",
            lambda k: "local" if k == "default_review_profile" else None,
        )
        result = _resolve_profile(None, template)
        assert result == "local"

    def test_fallback_to_sdk(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "squadron.cli.commands.review.get_config",
            lambda k: None,
        )
        result = _resolve_profile(None)
        assert result == "sdk"

    def test_model_inference_used_when_no_flag(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "squadron.cli.commands.review.get_config",
            lambda k: None,
        )
        result = _resolve_profile(None, model="gpt-4o")
        assert result == "openai"

    def test_flag_overrides_model_inference(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "squadron.cli.commands.review.get_config",
            lambda k: None,
        )
        result = _resolve_profile("local", model="gpt-4o")
        assert result == "local"


class TestInferProfileFromModel:
    """Test _infer_profile_from_model() pattern matching."""

    def test_opus_infers_sdk(self) -> None:
        assert _infer_profile_from_model("opus") == "sdk"

    def test_claude_prefix_infers_sdk(self) -> None:
        assert _infer_profile_from_model("claude-opus-4-6") == "sdk"

    def test_sonnet_infers_sdk(self) -> None:
        assert _infer_profile_from_model("sonnet") == "sdk"

    def test_haiku_infers_sdk(self) -> None:
        assert _infer_profile_from_model("haiku") == "sdk"

    def test_gpt_prefix_infers_openai(self) -> None:
        assert _infer_profile_from_model("gpt-4o") == "openai"

    def test_o3_prefix_infers_openai(self) -> None:
        assert _infer_profile_from_model("o3-mini") == "openai"

    def test_o1_prefix_infers_openai(self) -> None:
        assert _infer_profile_from_model("o1-preview") == "openai"

    def test_slash_infers_openrouter(self) -> None:
        assert _infer_profile_from_model("anthropic/claude-3.5-sonnet") == "openrouter"

    def test_unknown_model_returns_none(self) -> None:
        assert _infer_profile_from_model("llama3") is None


class TestCLIProfileFlag:
    """Test --profile flag wiring through CLI commands."""

    def test_run_review_command_passes_profile_to_execute(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify _run_review_command passes profile through."""
        from unittest.mock import AsyncMock, patch

        from squadron.cli.commands.review import _run_review_command
        from squadron.review.models import ReviewResult, Verdict

        mock_result = ReviewResult(
            verdict=Verdict.PASS,
            findings=[],
            raw_output="raw",
            template_name="arch",
            input_files={"input": "f.md"},
            model="opus",
        )

        # Mock template loading + getting
        monkeypatch.setattr(
            "squadron.cli.commands.review.load_all_templates",
            lambda: None,
        )
        monkeypatch.setattr(
            "squadron.cli.commands.review.get_template",
            lambda name: _make_template(profile="sdk"),
        )
        monkeypatch.setattr(
            "squadron.cli.commands.review.get_config",
            lambda k: None,
        )

        with patch(
            "squadron.cli.commands.review._execute_review",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_exec:
            _run_review_command(
                "arch",
                {"input": "f.md", "against": "a.md", "cwd": "."},
                "terminal",
                None,
                0,
                model_flag="opus",
                profile_flag="openrouter",
            )

        # Verify profile was passed through
        call_args = mock_exec.call_args
        assert call_args[1].get("profile") or call_args[0][4] == "openrouter"

    def test_run_review_command_defaults_to_sdk(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Without --profile, profile defaults to sdk."""
        from unittest.mock import AsyncMock, patch

        from squadron.cli.commands.review import _run_review_command
        from squadron.review.models import ReviewResult, Verdict

        mock_result = ReviewResult(
            verdict=Verdict.PASS,
            findings=[],
            raw_output="raw",
            template_name="arch",
            input_files={"input": "f.md"},
            model=None,
        )

        monkeypatch.setattr(
            "squadron.cli.commands.review.load_all_templates",
            lambda: None,
        )
        monkeypatch.setattr(
            "squadron.cli.commands.review.get_template",
            lambda name: _make_template(),
        )
        monkeypatch.setattr(
            "squadron.cli.commands.review.get_config",
            lambda k: None,
        )

        with patch(
            "squadron.cli.commands.review._execute_review",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_exec:
            _run_review_command(
                "arch",
                {"input": "f.md", "against": "a.md", "cwd": "."},
                "terminal",
                None,
                0,
            )

        # Default profile should be "sdk"
        call_args = mock_exec.call_args
        assert call_args[0][4] == "sdk"

    def test_profile_and_model_passed_together(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--profile and --model should both be forwarded."""
        from unittest.mock import AsyncMock, patch

        from squadron.cli.commands.review import _run_review_command
        from squadron.review.models import ReviewResult, Verdict

        mock_result = ReviewResult(
            verdict=Verdict.PASS,
            findings=[],
            raw_output="raw",
            template_name="arch",
            input_files={"input": "f.md"},
            model="gpt-4o",
        )

        monkeypatch.setattr(
            "squadron.cli.commands.review.load_all_templates",
            lambda: None,
        )
        monkeypatch.setattr(
            "squadron.cli.commands.review.get_template",
            lambda name: _make_template(),
        )
        monkeypatch.setattr(
            "squadron.cli.commands.review.get_config",
            lambda k: None,
        )

        with patch(
            "squadron.cli.commands.review._execute_review",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_exec:
            _run_review_command(
                "arch",
                {"input": "f.md", "against": "a.md", "cwd": "."},
                "terminal",
                None,
                0,
                model_flag="gpt-4o",
                profile_flag="openai",
            )

        # Both model and profile passed
        call_args = mock_exec.call_args
        assert call_args[0][3] == "gpt-4o"  # model
        assert call_args[0][4] == "openai"  # profile
