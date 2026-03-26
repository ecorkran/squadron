"""Tests for run_review_with_profile() provider-agnostic review execution."""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadron.review.models import ReviewResult, Verdict
from squadron.review.review_client import _write_prompt_log, run_review_with_profile
from squadron.review.templates import ReviewTemplate


def _make_template(
    profile: str | None = None,
    model: str | None = None,
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
        prompt_template="Review: {input}",
        profile=profile,
        model=model,
    )


# Sample review output that the parser can handle
_SAMPLE_REVIEW_OUTPUT = """\
**Verdict:** PASS

## Findings

### [PASS] — Code quality is good

The code follows best practices.
"""


class TestSDKDelegation:
    """Test that profile='sdk' delegates to run_review()."""

    @pytest.mark.asyncio
    async def test_sdk_profile_delegates_to_run_review(self) -> None:
        template = _make_template()
        inputs = {"input": "file.md"}
        mock_result = ReviewResult(
            verdict=Verdict.PASS,
            findings=[],
            raw_output="raw",
            template_name="test",
            input_files=inputs,
            model="opus",
        )

        with patch(
            "squadron.review.review_client.run_review",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            result = await run_review_with_profile(
                template,
                inputs,
                profile="sdk",
                rules_content="some rules",
                model="opus",
            )

        mock_run.assert_called_once_with(
            template,
            inputs,
            rules_content="some rules",
            model="opus",
        )
        assert result is mock_result


class TestNonSDKPath:
    """Test non-SDK provider routing."""

    @pytest.mark.asyncio
    async def test_openrouter_creates_client_with_correct_params(
        self,
    ) -> None:
        template = _make_template()
        inputs = {"input": "file.md"}

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = _SAMPLE_REVIEW_OUTPUT

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with (
            patch("squadron.review.review_client.get_profile") as mock_get_profile,
            patch(
                "squadron.review.review_client.AsyncOpenAI",
                return_value=mock_client,
            ) as mock_openai_cls,
            patch(
                "squadron.review.review_client._resolve_api_key",
                new_callable=AsyncMock,
                return_value="test-key",
            ),
        ):
            from squadron.providers.profiles import ProviderProfile

            mock_get_profile.return_value = ProviderProfile(
                name="openrouter",
                provider="openai",
                base_url="https://openrouter.ai/api/v1",
                api_key_env="OPENROUTER_API_KEY",
                default_headers={"X-Title": "squadron"},
            )

            result = await run_review_with_profile(
                template,
                inputs,
                profile="openrouter",
                model="anthropic/claude-3.5-sonnet",
            )

        # Verify AsyncOpenAI was created with correct params
        mock_openai_cls.assert_called_once()
        call_kwargs = mock_openai_cls.call_args[1]
        assert call_kwargs["api_key"] == "test-key"
        assert call_kwargs["base_url"] == "https://openrouter.ai/api/v1"
        assert call_kwargs["default_headers"] == {"X-Title": "squadron"}

        # Verify result is a valid ReviewResult
        assert isinstance(result, ReviewResult)
        assert result.template_name == "test"
        assert result.model == "anthropic/claude-3.5-sonnet"

    @pytest.mark.asyncio
    async def test_non_sdk_result_has_all_fields_for_auto_save(
        self,
    ) -> None:
        """SC9 parity: non-SDK ReviewResult must have all fields
        needed for auto-save and --json output."""
        template = _make_template()
        inputs = {"input": "file.md"}

        review_text = (
            "**Verdict:** CONCERNS\n\n"
            "## Findings\n\n"
            "### [CONCERN] — Minor issue\n\n"
            "Something to fix.\n"
        )

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = review_text

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with (
            patch("squadron.review.review_client.get_profile") as mock_get_profile,
            patch(
                "squadron.review.review_client.AsyncOpenAI",
                return_value=mock_client,
            ),
            patch(
                "squadron.review.review_client._resolve_api_key",
                new_callable=AsyncMock,
                return_value="test-key",
            ),
        ):
            from squadron.providers.profiles import ProviderProfile

            mock_get_profile.return_value = ProviderProfile(
                name="openai",
                provider="openai",
                api_key_env="OPENAI_API_KEY",
            )

            result = await run_review_with_profile(
                template,
                inputs,
                profile="openai",
                model="gpt-4o",
            )

        # All fields needed for auto-save and JSON
        assert result.verdict is not None
        assert result.template_name == "test"
        assert result.model == "gpt-4o"
        assert result.input_files == inputs
        assert result.timestamp is not None
        assert isinstance(result.findings, list)

        # to_dict() must work without errors
        d = result.to_dict()
        assert "verdict" in d
        assert "findings" in d
        assert "model" in d
        assert "template_name" in d

    @pytest.mark.asyncio
    async def test_unknown_profile_raises_error(self) -> None:
        template = _make_template()
        inputs = {"input": "file.md"}

        with pytest.raises(KeyError, match="not found"):
            await run_review_with_profile(
                template,
                inputs,
                profile="nonexistent",
                model="some-model",
            )

    @pytest.mark.asyncio
    async def test_missing_api_key_raises_error(self) -> None:
        template = _make_template()
        inputs = {"input": "file.md"}

        with (
            patch("squadron.review.review_client.get_profile") as mock_get_profile,
            patch(
                "squadron.review.review_client._resolve_api_key",
                new_callable=AsyncMock,
                side_effect=ValueError("No API key found"),
            ),
        ):
            from squadron.providers.profiles import ProviderProfile

            mock_get_profile.return_value = ProviderProfile(
                name="openai",
                provider="openai",
                api_key_env="OPENAI_API_KEY",
            )

            with pytest.raises(ValueError, match="No API key"):
                await run_review_with_profile(
                    template,
                    inputs,
                    profile="openai",
                    model="gpt-4o",
                )

    @pytest.mark.asyncio
    async def test_debug_output_at_verbosity_3(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """verbosity=3 → system prompt printed to stderr."""
        template = _make_template(model="test-model")
        inputs = {"input": "file.md"}

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = _SAMPLE_REVIEW_OUTPUT

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with (
            patch("squadron.review.review_client.get_profile") as mock_get_profile,
            patch(
                "squadron.review.review_client.AsyncOpenAI",
                return_value=mock_client,
            ),
            patch(
                "squadron.review.review_client._resolve_api_key",
                new_callable=AsyncMock,
                return_value="test-key",
            ),
        ):
            from squadron.providers.profiles import ProviderProfile

            mock_get_profile.return_value = ProviderProfile(
                name="openai",
                provider="openai",
                api_key_env="OPENAI_API_KEY",
            )
            await run_review_with_profile(
                template,
                inputs,
                profile="openai",
                model="test-model",
                verbosity=3,
            )

        captured = capsys.readouterr()
        assert "[DEBUG] System Prompt:" in captured.err
        assert "[DEBUG] User Prompt:" in captured.err

    @pytest.mark.asyncio
    async def test_no_debug_output_at_verbosity_2(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """verbosity=2 → nothing extra printed."""
        template = _make_template(model="test-model")
        inputs = {"input": "file.md"}

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = _SAMPLE_REVIEW_OUTPUT

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with (
            patch("squadron.review.review_client.get_profile") as mock_get_profile,
            patch(
                "squadron.review.review_client.AsyncOpenAI",
                return_value=mock_client,
            ),
            patch(
                "squadron.review.review_client._resolve_api_key",
                new_callable=AsyncMock,
                return_value="test-key",
            ),
        ):
            from squadron.providers.profiles import ProviderProfile

            mock_get_profile.return_value = ProviderProfile(
                name="openai",
                provider="openai",
                api_key_env="OPENAI_API_KEY",
            )
            await run_review_with_profile(
                template,
                inputs,
                profile="openai",
                model="test-model",
                verbosity=2,
            )

        captured = capsys.readouterr()
        assert "[DEBUG]" not in captured.err

    @pytest.mark.asyncio
    async def test_debug_rules_shown_when_present(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """rules_content non-empty + verbosity=3 → rules section printed."""
        template = _make_template(model="test-model")
        inputs = {"input": "file.md"}

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = _SAMPLE_REVIEW_OUTPUT

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with (
            patch("squadron.review.review_client.get_profile") as mock_get_profile,
            patch(
                "squadron.review.review_client.AsyncOpenAI",
                return_value=mock_client,
            ),
            patch(
                "squadron.review.review_client._resolve_api_key",
                new_callable=AsyncMock,
                return_value="test-key",
            ),
        ):
            from squadron.providers.profiles import ProviderProfile

            mock_get_profile.return_value = ProviderProfile(
                name="openai",
                provider="openai",
                api_key_env="OPENAI_API_KEY",
            )
            await run_review_with_profile(
                template,
                inputs,
                profile="openai",
                model="test-model",
                verbosity=3,
                rules_content="Always check for SQL injection.",
            )

        captured = capsys.readouterr()
        assert "[DEBUG] Injected Rules:" in captured.err
        assert "SQL injection" in captured.err

    @pytest.mark.asyncio
    async def test_no_model_raises_error(self) -> None:
        """Non-SDK path requires an explicit model."""
        template = _make_template(model=None)
        inputs = {"input": "file.md"}

        with (
            patch("squadron.review.review_client.get_profile") as mock_get_profile,
            patch(
                "squadron.review.review_client._resolve_api_key",
                new_callable=AsyncMock,
                return_value="test-key",
            ),
        ):
            from squadron.providers.profiles import ProviderProfile

            mock_get_profile.return_value = ProviderProfile(
                name="openai",
                provider="openai",
                api_key_env="OPENAI_API_KEY",
            )

            with pytest.raises(ValueError, match="No model specified"):
                await run_review_with_profile(
                    template,
                    inputs,
                    profile="openai",
                    model=None,
                )


# ---------------------------------------------------------------------------
# T8: Tests for _write_prompt_log()
# ---------------------------------------------------------------------------


class TestWritePromptLog:
    """Tests for _write_prompt_log()."""

    def test_creates_file(self, tmp_path: Path) -> None:
        path = _write_prompt_log(
            system_prompt="You are a reviewer.",
            user_prompt="Review this code.",
            rules_content="Check for SQL injection.",
            model="gpt-4o",
            profile="openai",
            template_name="code",
            log_dir=tmp_path,
        )
        assert path.exists()
        content = path.read_text()
        assert "## System Prompt" in content
        assert "You are a reviewer." in content
        assert "## User Prompt" in content
        assert "Review this code." in content
        assert "## Injected Rules" in content
        assert "SQL injection" in content

    def test_filename_format(self, tmp_path: Path) -> None:
        path = _write_prompt_log(
            system_prompt="sys",
            user_prompt="usr",
            rules_content=None,
            model="opus",
            profile="sdk",
            template_name="slice",
            log_dir=tmp_path,
        )
        assert re.match(r"review-prompt-\d{8}-\d{6}\.md", path.name), (
            f"Unexpected filename: {path.name}"
        )

    def test_contains_metadata(self, tmp_path: Path) -> None:
        path = _write_prompt_log(
            system_prompt="sys",
            user_prompt="usr",
            rules_content=None,
            model="gpt-4o",
            profile="openrouter",
            template_name="tasks",
            log_dir=tmp_path,
        )
        content = path.read_text()
        assert "template: tasks" in content
        assert "model: gpt-4o" in content
        assert "profile: openrouter" in content
        assert "timestamp:" in content

    def test_no_rules(self, tmp_path: Path) -> None:
        path = _write_prompt_log(
            system_prompt="sys",
            user_prompt="usr",
            rules_content=None,
            model="opus",
            profile="sdk",
            template_name="code",
            log_dir=tmp_path,
        )
        content = path.read_text()
        assert "## Injected Rules" in content
        assert "\nNone\n" in content


# ---------------------------------------------------------------------------
# T10: Tests for prompt capture and logging wiring
# ---------------------------------------------------------------------------


class TestPromptCaptureWiring:
    """Tests for prompt capture at various verbosity levels."""

    @pytest.mark.asyncio
    async def test_verbosity_2_populates_prompt_fields(self) -> None:
        template = _make_template(model="test-model")
        inputs = {"input": "file.md"}

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = _SAMPLE_REVIEW_OUTPUT

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with (
            patch("squadron.review.review_client.get_profile") as mock_get_profile,
            patch(
                "squadron.review.review_client.AsyncOpenAI",
                return_value=mock_client,
            ),
            patch(
                "squadron.review.review_client._resolve_api_key",
                new_callable=AsyncMock,
                return_value="test-key",
            ),
        ):
            from squadron.providers.profiles import ProviderProfile

            mock_get_profile.return_value = ProviderProfile(
                name="openai",
                provider="openai",
                api_key_env="OPENAI_API_KEY",
            )
            result = await run_review_with_profile(
                template,
                inputs,
                profile="openai",
                model="test-model",
                verbosity=2,
            )

        assert result.system_prompt is not None
        assert result.user_prompt is not None

    @pytest.mark.asyncio
    async def test_verbosity_1_no_prompt_fields(self) -> None:
        template = _make_template(model="test-model")
        inputs = {"input": "file.md"}

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = _SAMPLE_REVIEW_OUTPUT

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with (
            patch("squadron.review.review_client.get_profile") as mock_get_profile,
            patch(
                "squadron.review.review_client.AsyncOpenAI",
                return_value=mock_client,
            ),
            patch(
                "squadron.review.review_client._resolve_api_key",
                new_callable=AsyncMock,
                return_value="test-key",
            ),
        ):
            from squadron.providers.profiles import ProviderProfile

            mock_get_profile.return_value = ProviderProfile(
                name="openai",
                provider="openai",
                api_key_env="OPENAI_API_KEY",
            )
            result = await run_review_with_profile(
                template,
                inputs,
                profile="openai",
                model="test-model",
                verbosity=1,
            )

        assert result.system_prompt is None

    @pytest.mark.asyncio
    async def test_verbosity_3_writes_prompt_log(self) -> None:
        template = _make_template(model="test-model")
        inputs = {"input": "file.md"}

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = _SAMPLE_REVIEW_OUTPUT

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with (
            patch("squadron.review.review_client.get_profile") as mock_get_profile,
            patch(
                "squadron.review.review_client.AsyncOpenAI",
                return_value=mock_client,
            ),
            patch(
                "squadron.review.review_client._resolve_api_key",
                new_callable=AsyncMock,
                return_value="test-key",
            ),
            patch(
                "squadron.review.review_client._write_prompt_log",
                return_value=Path("/tmp/test-log.md"),
            ) as mock_write_log,
        ):
            from squadron.providers.profiles import ProviderProfile

            mock_get_profile.return_value = ProviderProfile(
                name="openai",
                provider="openai",
                api_key_env="OPENAI_API_KEY",
            )
            await run_review_with_profile(
                template,
                inputs,
                profile="openai",
                model="test-model",
                verbosity=3,
            )

        mock_write_log.assert_called_once()

    @pytest.mark.asyncio
    async def test_verbosity_3_prints_log_path(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        template = _make_template(model="test-model")
        inputs = {"input": "file.md"}

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = _SAMPLE_REVIEW_OUTPUT

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with (
            patch("squadron.review.review_client.get_profile") as mock_get_profile,
            patch(
                "squadron.review.review_client.AsyncOpenAI",
                return_value=mock_client,
            ),
            patch(
                "squadron.review.review_client._resolve_api_key",
                new_callable=AsyncMock,
                return_value="test-key",
            ),
            patch(
                "squadron.review.review_client._write_prompt_log",
                return_value=Path("/tmp/test-log.md"),
            ),
        ):
            from squadron.providers.profiles import ProviderProfile

            mock_get_profile.return_value = ProviderProfile(
                name="openai",
                provider="openai",
                api_key_env="OPENAI_API_KEY",
            )
            await run_review_with_profile(
                template,
                inputs,
                profile="openai",
                model="test-model",
                verbosity=3,
            )

        captured = capsys.readouterr()
        assert "Prompt log:" in captured.err
        assert "test-log.md" in captured.err
