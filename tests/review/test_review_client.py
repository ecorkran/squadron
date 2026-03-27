"""Tests for run_review_with_profile() — unified provider-agnostic execution."""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadron.core.models import AgentConfig, AgentState, Message, MessageType
from squadron.providers.base import ProviderCapabilities
from squadron.review.models import ReviewResult
from squadron.review.review_client import _write_prompt_log, run_review_with_profile
from squadron.review.templates import ReviewTemplate

_P = "squadron.review.review_client"


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


def _make_mock_agent(response_text: str = _SAMPLE_REVIEW_OUTPUT) -> MagicMock:
    """Create a mock Agent that yields a single Message with given text."""
    agent = MagicMock()
    agent.state = AgentState.idle
    agent.shutdown = AsyncMock()

    async def _handle(message: Message) -> AsyncIterator[Message]:
        yield Message(
            sender="mock-agent",
            recipients=[],
            content=response_text,
            message_type=MessageType.chat,
        )

    agent.handle_message = _handle
    return agent


def _make_mock_provider(
    *,
    can_read_files: bool = False,
    agent: MagicMock | None = None,
) -> MagicMock:
    """Create a mock AgentProvider with given capabilities."""
    provider = MagicMock()
    provider.capabilities = ProviderCapabilities(can_read_files=can_read_files)
    provider.create_agent = AsyncMock(return_value=agent or _make_mock_agent())
    return provider


class TestUnifiedPath:
    """All profiles route through the same provider registry path."""

    @pytest.mark.asyncio
    async def test_openai_profile_routes_through_registry(self) -> None:
        template = _make_template()
        inputs = {"input": "file.md"}
        mock_provider = _make_mock_provider()

        with (
            patch(f"{_P}.get_profile") as mock_get_profile,
            patch(f"{_P}.get_provider", return_value=mock_provider),
            patch(f"{_P}._ensure_provider_loaded"),
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

        assert isinstance(result, ReviewResult)
        assert result.template_name == "test"
        mock_provider.create_agent.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_sdk_profile_routes_through_registry(self) -> None:
        template = _make_template()
        inputs = {"input": "file.md"}
        mock_provider = _make_mock_provider(can_read_files=True)

        with (
            patch(f"{_P}.get_profile") as mock_get_profile,
            patch(f"{_P}.get_provider", return_value=mock_provider),
            patch(f"{_P}._ensure_provider_loaded"),
        ):
            from squadron.providers.base import AuthType, ProfileName, ProviderType
            from squadron.providers.profiles import ProviderProfile

            mock_get_profile.return_value = ProviderProfile(
                name=ProfileName.SDK,
                provider=ProviderType.SDK,
                auth_type=AuthType.SESSION,
            )
            result = await run_review_with_profile(
                template,
                inputs,
                profile="sdk",
            )

        assert isinstance(result, ReviewResult)
        mock_provider.create_agent.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_codex_profile_routes_through_registry(self) -> None:
        template = _make_template()
        inputs = {"input": "file.md"}
        mock_provider = _make_mock_provider(can_read_files=True)

        with (
            patch(f"{_P}.get_profile") as mock_get_profile,
            patch(f"{_P}.get_provider", return_value=mock_provider),
            patch(f"{_P}._ensure_provider_loaded"),
        ):
            from squadron.providers.base import AuthType, ProfileName, ProviderType
            from squadron.providers.profiles import ProviderProfile

            mock_get_profile.return_value = ProviderProfile(
                name=ProfileName.OPENAI_OAUTH,
                provider=ProviderType.OPENAI_OAUTH,
                auth_type=AuthType.OAUTH,
            )
            result = await run_review_with_profile(
                template,
                inputs,
                profile="openai-oauth",
                model="gpt-5.3-codex",
            )

        assert isinstance(result, ReviewResult)
        mock_provider.create_agent.assert_awaited_once()


class TestFileInjection:
    """File injection based on provider capabilities."""

    @pytest.mark.asyncio
    async def test_injection_when_cannot_read_files(self, tmp_path: Path) -> None:
        test_file = tmp_path / "code.py"
        test_file.write_text("print('hello')")

        template = _make_template()
        inputs = {"input": str(test_file)}
        mock_agent = _make_mock_agent()
        mock_provider = _make_mock_provider(can_read_files=False, agent=mock_agent)

        with (
            patch(f"{_P}.get_profile") as mock_get_profile,
            patch(f"{_P}.get_provider", return_value=mock_provider),
            patch(f"{_P}._ensure_provider_loaded"),
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
                model="gpt-4o",
            )

        # The prompt sent to handle_message should contain the file contents
        config = mock_provider.create_agent.call_args[0][0]
        assert isinstance(config, AgentConfig)

    @pytest.mark.asyncio
    async def test_no_injection_when_can_read_files(self, tmp_path: Path) -> None:
        test_file = tmp_path / "code.py"
        test_file.write_text("print('hello')")

        template = _make_template()
        inputs = {"input": str(test_file)}
        mock_provider = _make_mock_provider(can_read_files=True)

        with (
            patch(f"{_P}.get_profile") as mock_get_profile,
            patch(f"{_P}.get_provider", return_value=mock_provider),
            patch(f"{_P}._ensure_provider_loaded"),
            patch(f"{_P}._inject_file_contents") as mock_inject,
        ):
            from squadron.providers.base import AuthType, ProviderType
            from squadron.providers.profiles import ProviderProfile

            mock_get_profile.return_value = ProviderProfile(
                name="sdk",
                provider=ProviderType.SDK,
                auth_type=AuthType.SESSION,
            )
            await run_review_with_profile(
                template,
                inputs,
                profile="sdk",
            )

        mock_inject.assert_not_called()


class TestVerbosity:
    """Verbosity controls debug output and prompt capture."""

    @pytest.mark.asyncio
    async def test_debug_output_at_verbosity_3(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        template = _make_template(model="test-model")
        inputs = {"input": "file.md"}
        mock_provider = _make_mock_provider()

        with (
            patch(f"{_P}.get_profile") as mock_get_profile,
            patch(f"{_P}.get_provider", return_value=mock_provider),
            patch(f"{_P}._ensure_provider_loaded"),
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
        assert "[DEBUG] System Prompt:" in captured.err
        assert "[DEBUG] User Prompt:" in captured.err

    @pytest.mark.asyncio
    async def test_no_debug_at_verbosity_2(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        template = _make_template(model="test-model")
        inputs = {"input": "file.md"}
        mock_provider = _make_mock_provider()

        with (
            patch(f"{_P}.get_profile") as mock_get_profile,
            patch(f"{_P}.get_provider", return_value=mock_provider),
            patch(f"{_P}._ensure_provider_loaded"),
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
    async def test_verbosity_2_populates_prompt_fields(self) -> None:
        template = _make_template(model="test-model")
        inputs = {"input": "file.md"}
        mock_provider = _make_mock_provider()

        with (
            patch(f"{_P}.get_profile") as mock_get_profile,
            patch(f"{_P}.get_provider", return_value=mock_provider),
            patch(f"{_P}._ensure_provider_loaded"),
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
        mock_provider = _make_mock_provider()

        with (
            patch(f"{_P}.get_profile") as mock_get_profile,
            patch(f"{_P}.get_provider", return_value=mock_provider),
            patch(f"{_P}._ensure_provider_loaded"),
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
        mock_provider = _make_mock_provider()

        with (
            patch(f"{_P}.get_profile") as mock_get_profile,
            patch(f"{_P}.get_provider", return_value=mock_provider),
            patch(f"{_P}._ensure_provider_loaded"),
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
    async def test_debug_rules_shown_when_present(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        template = _make_template(model="test-model")
        inputs = {"input": "file.md"}
        mock_provider = _make_mock_provider()

        with (
            patch(f"{_P}.get_profile") as mock_get_profile,
            patch(f"{_P}.get_provider", return_value=mock_provider),
            patch(f"{_P}._ensure_provider_loaded"),
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
                rules_content="Always check for SQL injection.",
            )

        captured = capsys.readouterr()
        assert "[DEBUG] Injected Rules:" in captured.err
        assert "SQL injection" in captured.err


class TestEdgeCases:
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
    async def test_result_has_all_fields(self) -> None:
        review_text = (
            "**Verdict:** CONCERNS\n\n"
            "## Findings\n\n"
            "### [CONCERN] — Minor issue\n\n"
            "Something to fix.\n"
        )
        template = _make_template()
        inputs = {"input": "file.md"}
        mock_provider = _make_mock_provider(agent=_make_mock_agent(review_text))

        with (
            patch(f"{_P}.get_profile") as mock_get_profile,
            patch(f"{_P}.get_provider", return_value=mock_provider),
            patch(f"{_P}._ensure_provider_loaded"),
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

        assert result.verdict is not None
        assert result.template_name == "test"
        assert result.model == "gpt-4o"
        assert result.input_files == inputs
        assert isinstance(result.findings, list)
        d = result.to_dict()
        assert "verdict" in d


# ---------------------------------------------------------------------------
# _write_prompt_log tests (unchanged)
# ---------------------------------------------------------------------------


class TestWritePromptLog:
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
        assert re.match(r"review-prompt-\d{8}-\d{6}\.md", path.name)

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
        assert "\nNone\n" in content
