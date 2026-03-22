"""Tests for _resolve_profile() resolution chain."""

from __future__ import annotations

import pytest

from squadron.cli.commands.review import _resolve_profile
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

    def test_no_model_inference_in_resolve_profile(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_resolve_profile no longer infers from model — alias resolution
        handles this upstream in _run_review_command()."""
        monkeypatch.setattr(
            "squadron.cli.commands.review.get_config",
            lambda k: None,
        )
        # Without flag or template, falls through to sdk default
        result = _resolve_profile(None)
        assert result == "sdk"


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
            model="gpt-5.4-nano",
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


class TestAliasWiring:
    """Test alias resolution wiring in _run_review_command()."""

    def test_alias_resolves_model_and_profile(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """model_flag='gpt54-nano' resolves to model='gpt-5.4-nano', profile='openai'."""
        from unittest.mock import AsyncMock, patch

        from squadron.cli.commands.review import _run_review_command
        from squadron.review.models import ReviewResult, Verdict

        mock_result = ReviewResult(
            verdict=Verdict.PASS,
            findings=[],
            raw_output="raw",
            template_name="slice",
            input_files={"input": "f.md"},
            model="gpt-5.4-nano",
        )

        monkeypatch.setattr(
            "squadron.cli.commands.review.load_all_templates", lambda: None
        )
        monkeypatch.setattr(
            "squadron.cli.commands.review.get_template",
            lambda name: _make_template(),
        )
        monkeypatch.setattr("squadron.cli.commands.review.get_config", lambda k: None)

        with patch(
            "squadron.cli.commands.review._execute_review",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_exec:
            _run_review_command(
                "slice",
                {"input": "f.md", "against": "a.md", "cwd": "."},
                "terminal",
                None,
                0,
                model_flag="gpt54-nano",
            )

        call_args = mock_exec.call_args
        assert call_args[0][3] == "gpt-5.4-nano"  # resolved model
        assert call_args[0][4] == "openai"  # resolved profile

    def test_unknown_model_passes_through(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Unknown model passes through unchanged, profile falls to sdk."""
        from unittest.mock import AsyncMock, patch

        from squadron.cli.commands.review import _run_review_command
        from squadron.review.models import ReviewResult, Verdict

        mock_result = ReviewResult(
            verdict=Verdict.PASS,
            findings=[],
            raw_output="raw",
            template_name="slice",
            input_files={"input": "f.md"},
            model="llama-3-70b",
        )

        monkeypatch.setattr(
            "squadron.cli.commands.review.load_all_templates", lambda: None
        )
        monkeypatch.setattr(
            "squadron.cli.commands.review.get_template",
            lambda name: _make_template(),
        )
        monkeypatch.setattr("squadron.cli.commands.review.get_config", lambda k: None)

        with patch(
            "squadron.cli.commands.review._execute_review",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_exec:
            _run_review_command(
                "slice",
                {"input": "f.md", "against": "a.md", "cwd": "."},
                "terminal",
                None,
                0,
                model_flag="llama-3-70b",
            )

        call_args = mock_exec.call_args
        assert call_args[0][3] == "llama-3-70b"  # unchanged
        assert call_args[0][4] == "sdk"  # default fallback

    def test_explicit_profile_overrides_alias(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Explicit --profile flag overrides alias-inferred profile."""
        from unittest.mock import AsyncMock, patch

        from squadron.cli.commands.review import _run_review_command
        from squadron.review.models import ReviewResult, Verdict

        mock_result = ReviewResult(
            verdict=Verdict.PASS,
            findings=[],
            raw_output="raw",
            template_name="slice",
            input_files={"input": "f.md"},
            model="gpt-5.4-nano",
        )

        monkeypatch.setattr(
            "squadron.cli.commands.review.load_all_templates", lambda: None
        )
        monkeypatch.setattr(
            "squadron.cli.commands.review.get_template",
            lambda name: _make_template(),
        )
        monkeypatch.setattr("squadron.cli.commands.review.get_config", lambda k: None)

        with patch(
            "squadron.cli.commands.review._execute_review",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_exec:
            _run_review_command(
                "slice",
                {"input": "f.md", "against": "a.md", "cwd": "."},
                "terminal",
                None,
                0,
                model_flag="gpt54-nano",
                profile_flag="local",
            )

        call_args = mock_exec.call_args
        assert call_args[0][3] == "gpt-5.4-nano"  # alias-resolved model
        assert call_args[0][4] == "local"  # explicit flag wins
