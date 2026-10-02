"""Tests for run_review_with_profile() — unified provider-agnostic execution."""

from __future__ import annotations

import logging
import re
from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadron.core.models import AgentConfig, AgentState, Effort, Message, MessageType
from squadron.providers.base import ProviderCapabilities
from squadron.providers.errors import EmptyFinalTurnError
from squadron.review.git_utils import EmptyDiffError
from squadron.review.models import ReviewResult
from squadron.review.review_client import InjectedPrompt, _write_prompt_log, run_review_with_profile
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
            patch(f"{_P}.ensure_provider_loaded"),
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
            patch(f"{_P}.ensure_provider_loaded"),
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
            patch(f"{_P}.ensure_provider_loaded"),
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
            patch(f"{_P}.ensure_provider_loaded"),
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
            patch(f"{_P}.ensure_provider_loaded"),
            patch(
                f"{_P}._inject_file_contents",
                side_effect=lambda p, *a, **k: InjectedPrompt(p, None),
            ) as mock_inject,
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

        # Injection is now always invoked — the diff must reach the model even when the
        # provider can read files — but file *bodies* are suppressed (issue #81).
        mock_inject.assert_called_once()
        assert mock_inject.call_args.kwargs["include_bodies"] is False


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
            patch(f"{_P}.ensure_provider_loaded"),
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
            patch(f"{_P}.ensure_provider_loaded"),
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
            patch(f"{_P}.ensure_provider_loaded"),
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
            patch(f"{_P}.ensure_provider_loaded"),
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
            patch(f"{_P}.ensure_provider_loaded"),
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
            patch(f"{_P}.ensure_provider_loaded"),
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
            "**Verdict:** CONCERNS\n\n## Findings\n\n### [CONCERN] — Minor issue\n\nSomething to fix.\n"
        )
        template = _make_template()
        inputs = {"input": "file.md"}
        mock_provider = _make_mock_provider(agent=_make_mock_agent(review_text))

        with (
            patch(f"{_P}.get_profile") as mock_get_profile,
            patch(f"{_P}.get_provider", return_value=mock_provider),
            patch(f"{_P}.ensure_provider_loaded"),
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

    @pytest.mark.asyncio
    async def test_raw_output_excludes_tool_call_noise(self) -> None:
        """Issue #22: tool_use/tool_result messages must not corrupt raw_output.

        SDK reviews interleave assistant prose with tool-call narration
        ("Using tool: Bash") and tool results (command stdout). Bare
        concatenation with no separator and no filtering previously mashed
        these into the review's raw_output, corrupting the very
        ### [SEVERITY] structure the parser depends on.
        """
        template = _make_template()
        inputs = {"input": "file.md"}

        async def _handle(message: Message) -> AsyncIterator[Message]:
            yield Message(
                sender="mock-agent",
                recipients=[],
                content="Let me check the diff first.",
                message_type=MessageType.chat,
                metadata={"sdk_type": "assistant_text"},
            )
            yield Message(
                sender="mock-agent",
                recipients=[],
                content="Using tool: Bash",
                message_type=MessageType.system,
                metadata={"sdk_type": "tool_use"},
            )
            yield Message(
                sender="mock-agent",
                recipients=[],
                content="<diff output>",
                message_type=MessageType.system,
                metadata={"sdk_type": "tool_result"},
            )
            yield Message(
                sender="mock-agent",
                recipients=[],
                content=_SAMPLE_REVIEW_OUTPUT,
                message_type=MessageType.chat,
                metadata={"sdk_type": "assistant_text"},
            )

        agent = MagicMock()
        agent.state = AgentState.idle
        agent.shutdown = AsyncMock()
        agent.handle_message = _handle
        mock_provider = _make_mock_provider(agent=agent)

        with (
            patch(f"{_P}.get_profile") as mock_get_profile,
            patch(f"{_P}.get_provider", return_value=mock_provider),
            patch(f"{_P}.ensure_provider_loaded"),
        ):
            from squadron.providers.profiles import ProviderProfile

            mock_get_profile.return_value = ProviderProfile(
                name="sdk",
                provider="sdk",
                api_key_env=None,
            )
            result = await run_review_with_profile(
                template,
                inputs,
                profile="sdk",
                model="claude-sonnet-5",
            )

        assert "Using tool:" not in result.raw_output
        assert "<diff output>" not in result.raw_output
        assert result.raw_output == f"Let me check the diff first.\n{_SAMPLE_REVIEW_OUTPUT}"


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


# ---------------------------------------------------------------------------
# Tool-use telemetry carried onto ReviewResult (slice 265, task 21)
# ---------------------------------------------------------------------------


class TestReviewResultToolTelemetry:
    def _provider_yielding(self, metadata: dict[str, object] | None) -> MagicMock:
        agent = MagicMock()
        agent.state = AgentState.idle
        agent.shutdown = AsyncMock()

        async def _handle(message: Message) -> AsyncIterator[Message]:
            yield Message(
                sender="mock-agent",
                recipients=[],
                content=_SAMPLE_REVIEW_OUTPUT,
                message_type=MessageType.chat,
                metadata=metadata or {},
            )

        agent.handle_message = _handle
        provider = MagicMock()
        provider.capabilities = ProviderCapabilities(can_read_files=False)
        provider.create_agent = AsyncMock(return_value=agent)
        return provider

    async def _run(self, metadata: dict[str, object] | None) -> ReviewResult:
        from squadron.providers.profiles import ProviderProfile

        with (
            patch(f"{_P}.get_profile") as mock_get_profile,
            patch(f"{_P}.get_provider", return_value=self._provider_yielding(metadata)),
            patch(f"{_P}.ensure_provider_loaded"),
        ):
            mock_get_profile.return_value = ProviderProfile(
                name="openai", provider="openai", api_key_env="OPENAI_API_KEY"
            )
            return await run_review_with_profile(
                _make_template(), {"input": "file.md"}, profile="openai"
            )

    @pytest.mark.asyncio
    async def test_telemetry_from_final_message_lands_on_result(self) -> None:
        result = await self._run({"tools_given": ["read_file", "grep"], "tool_calls_made": 4})

        assert result.tools_given == ["read_file", "grep"]
        assert result.tool_calls_made == 4

    @pytest.mark.asyncio
    async def test_zero_calls_is_preserved_not_collapsed_to_none(self) -> None:
        result = await self._run({"tools_given": ["read_file"], "tool_calls_made": 0})

        assert result.tools_given == ["read_file"]
        assert result.tool_calls_made == 0

    @pytest.mark.asyncio
    async def test_no_telemetry_leaves_fields_none(self) -> None:
        result = await self._run(None)

        assert result.tools_given is None
        assert result.tool_calls_made is None

    @pytest.mark.asyncio
    async def test_zero_calls_logs_a_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """The failure mode is silent otherwise: a verdict from a model that read nothing."""
        with caplog.at_level(logging.WARNING, logger="squadron.review.review_client"):
            await self._run({"tools_given": ["read_file"], "tool_calls_made": 0})

        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert any("no tool calls" in r.getMessage() for r in warnings)

    @pytest.mark.asyncio
    async def test_calls_made_logs_no_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.WARNING, logger="squadron.review.review_client"):
            await self._run({"tools_given": ["read_file"], "tool_calls_made": 4})

        assert not [r for r in caplog.records if "no tool calls" in r.getMessage()]


class TestStopReasonEvidenceReadBack:
    """Slice 918 T2.5: the three stamped keys reach ``ReviewResult``.

    Asserted here rather than only end-to-end because a read-back typo is a wiring
    mistake the digest test would surface late and indirectly — as a missing line in
    rendered markdown, not as a wrong assignment.

    Delegates to the harness above rather than subclassing it: inheritance would make
    pytest re-collect every parent test under this class's name, reporting five extra
    passes that assert nothing new.
    """

    async def _run(self, metadata: dict[str, object] | None) -> ReviewResult:
        return await TestReviewResultToolTelemetry()._run(metadata)  # pyright: ignore[reportPrivateUsage]

    @pytest.mark.asyncio
    async def test_stamped_openrouter_run_lands_all_three(self) -> None:
        result = await self._run(
            {
                "tools_given": ["read_file"],
                "tool_calls_made": 2,
                "stop_reason": "length",
                "reasoning_chars": 4096,
                "failed_tool_calls": 2,
            }
        )

        assert result.stop_reason == "length"
        assert result.reasoning_chars == 4096
        assert result.failed_tool_calls == 2

    @pytest.mark.asyncio
    async def test_sdk_path_run_leaves_all_three_none(self) -> None:
        """The SDK provider stamps none of the three (D12); nothing invents a value."""
        result = await self._run({"sdk_type": "assistant_text"})

        assert result.stop_reason is None
        assert result.reasoning_chars is None
        assert result.failed_tool_calls is None

    @pytest.mark.asyncio
    async def test_zero_failed_calls_is_preserved_not_collapsed_to_none(self) -> None:
        """A stamped 0 must survive the read-back as 0.

        The guard is ``is not None``, not truthiness: collapsing a real zero here would
        make a healthy instrumented run look uninstrumented to the JSON consumer.
        """
        result = await self._run(
            {
                "tools_given": ["read_file"],
                "tool_calls_made": 3,
                "stop_reason": "stop",
                "reasoning_chars": 0,
                "failed_tool_calls": 0,
            }
        )

        assert result.failed_tool_calls == 0
        assert result.reasoning_chars == 0
        assert result.stop_reason == "stop"


class TestDiffCoverageCap:
    """Slice 927 D4: a truncated diff with no successful tool call caps PASS to CONCERNS."""

    @staticmethod
    def _profile() -> object:
        from squadron.providers.profiles import ProviderProfile

        return ProviderProfile(name="openai", provider="openai", api_key_env="OPENAI_API_KEY")

    @pytest.mark.asyncio
    async def test_truncated_diff_zero_tool_calls_pass_becomes_concerns(
        self, patch_config_paths
    ) -> None:
        from squadron.config.manager import set_config
        from squadron.review.models import Verdict, VerdictSource

        set_config("review.max_file_size_bytes", "100")
        mock_provider = _make_mock_provider()

        with (
            patch(f"{_P}.get_profile", return_value=self._profile()),
            patch(f"{_P}.get_provider", return_value=mock_provider),
            patch(f"{_P}.ensure_provider_loaded"),
            patch(f"{_P}._run_git_diff_filenames", return_value={"src/foo.py"}),
            patch(f"{_P}._run_git_diff", return_value="x" * 500),
        ):
            result = await run_review_with_profile(
                _make_template(),
                {"diff": "abc123...HEAD", "input": "file.md"},
                profile="openai",
            )

        assert result.verdict is Verdict.CONCERNS
        assert result.verdict_source is VerdictSource.IMPOSED
        assert result.diff_injection is not None
        assert result.diff_injection.truncated is True
        assert result.findings[0].category == "review-coverage"


class TestAnsweringModelAssignment:
    """Slice 927 C.6/C.7, D9-D12: result.model follows the answering model."""

    @staticmethod
    def _profile() -> object:
        from squadron.providers.profiles import ProviderProfile

        return ProviderProfile(name="openai", provider="openai", api_key_env="OPENAI_API_KEY")

    @staticmethod
    def _mock_agent_stamping(answering_models: list[str]) -> MagicMock:
        agent = MagicMock()
        agent.state = AgentState.idle
        agent.shutdown = AsyncMock()

        async def _handle(message: Message) -> AsyncIterator[Message]:
            yield Message(
                sender="mock-agent",
                recipients=[],
                content=_SAMPLE_REVIEW_OUTPUT,
                message_type=MessageType.chat,
                metadata={"answering_models": answering_models},
            )

        agent.handle_message = _handle
        return agent

    @pytest.mark.asyncio
    async def test_substitution_sets_model_and_warns(self, caplog: pytest.LogCaptureFixture) -> None:
        agent = self._mock_agent_stamping(["gpt-4.1"])
        mock_provider = _make_mock_provider(agent=agent)

        with (
            caplog.at_level("WARNING", logger="squadron.review.review_client"),
            patch(f"{_P}.get_profile", return_value=self._profile()),
            patch(f"{_P}.get_provider", return_value=mock_provider),
            patch(f"{_P}.ensure_provider_loaded"),
        ):
            result = await run_review_with_profile(
                _make_template(),
                {"input": "file.md"},
                profile="openai",
                model="gpt-5",
            )

        assert result.model == "gpt-4.1"
        assert result.requested_model == "gpt-5"
        assert result.model_substituted is True
        assert any("requested model gpt-5 but gpt-4.1 answered" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_snapshot_answer_no_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        agent = self._mock_agent_stamping(["gpt-5-2025-08-07"])
        mock_provider = _make_mock_provider(agent=agent)

        with (
            caplog.at_level("WARNING", logger="squadron.review.review_client"),
            patch(f"{_P}.get_profile", return_value=self._profile()),
            patch(f"{_P}.get_provider", return_value=mock_provider),
            patch(f"{_P}.ensure_provider_loaded"),
        ):
            result = await run_review_with_profile(
                _make_template(),
                {"input": "file.md"},
                profile="openai",
                model="gpt-5",
            )

        assert result.model == "gpt-5-2025-08-07"
        assert result.model_substituted is False
        assert not any("but" in r.message and "answered" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_no_stamp_keeps_requested_id_no_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        agent = self._mock_agent_stamping([])
        mock_provider = _make_mock_provider(agent=agent)

        with (
            caplog.at_level("WARNING", logger="squadron.review.review_client"),
            patch(f"{_P}.get_profile", return_value=self._profile()),
            patch(f"{_P}.get_provider", return_value=mock_provider),
            patch(f"{_P}.ensure_provider_loaded"),
        ):
            result = await run_review_with_profile(
                _make_template(),
                {"input": "file.md"},
                profile="openai",
                model="gpt-5.3-codex",
            )

        assert result.model == "gpt-5.3-codex"
        assert result.answering_models == []
        assert not any("answered" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_two_models_last_wins_and_warns_naming_both(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        agent = self._mock_agent_stamping(["gpt-4.1", "gpt-5"])
        mock_provider = _make_mock_provider(agent=agent)

        with (
            caplog.at_level("WARNING", logger="squadron.review.review_client"),
            patch(f"{_P}.get_profile", return_value=self._profile()),
            patch(f"{_P}.get_provider", return_value=mock_provider),
            patch(f"{_P}.ensure_provider_loaded"),
        ):
            result = await run_review_with_profile(
                _make_template(),
                {"input": "file.md"},
                profile="openai",
                model="gpt-5",
            )

        assert result.model == "gpt-5"
        assert result.answering_models == ["gpt-4.1", "gpt-5"]
        multi_model_warnings = [r for r in caplog.records if "more than one model" in r.message]
        assert len(multi_model_warnings) == 1
        assert "gpt-4.1" in multi_model_warnings[0].message
        assert "gpt-5" in multi_model_warnings[0].message


class TestEmptyDiffRefusesToRun:
    """A diff-based review with no changed files must not reach the model (#73)."""

    @staticmethod
    def _profile() -> object:
        from squadron.providers.profiles import ProviderProfile

        return ProviderProfile(name="openai", provider="openai", api_key_env="OPENAI_API_KEY")

    @pytest.mark.asyncio
    async def test_empty_diff_raises_before_the_model_is_called(self) -> None:
        mock_provider = _make_mock_provider()

        with (
            patch(f"{_P}.get_profile", return_value=self._profile()),
            patch(f"{_P}.get_provider", return_value=mock_provider),
            patch(f"{_P}.ensure_provider_loaded"),
            patch(f"{_P}._run_git_diff_filenames", return_value=set()),
            pytest.raises(EmptyDiffError, match="nothing to review"),
        ):
            await run_review_with_profile(
                _make_template(),
                {"diff": "abc123...HEAD"},
                profile="openai",
            )

        # The point of failing early: no agent was ever constructed, so no
        # non-review can reach persistence and overwrite a real one.
        mock_provider.create_agent.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_non_empty_diff_still_runs(self) -> None:
        mock_provider = _make_mock_provider()

        with (
            patch(f"{_P}.get_profile", return_value=self._profile()),
            patch(f"{_P}.get_provider", return_value=mock_provider),
            patch(f"{_P}.ensure_provider_loaded"),
            patch(f"{_P}._run_git_diff_filenames", return_value={"src/foo.py"}),
        ):
            result = await run_review_with_profile(
                _make_template(),
                {"diff": "abc123...HEAD", "input": "file.md"},
                profile="openai",
            )

        assert isinstance(result, ReviewResult)
        mock_provider.create_agent.assert_awaited()

    @pytest.mark.asyncio
    async def test_template_without_a_diff_input_is_unaffected(self) -> None:
        """Non-code templates resolve no diff and must not be gated on one."""
        mock_provider = _make_mock_provider()

        with (
            patch(f"{_P}.get_profile", return_value=self._profile()),
            patch(f"{_P}.get_provider", return_value=mock_provider),
            patch(f"{_P}.ensure_provider_loaded"),
        ):
            result = await run_review_with_profile(
                _make_template(),
                {"input": "file.md"},
                profile="openai",
            )

        assert isinstance(result, ReviewResult)


class TestDefaultSystemPromptPreset:
    """#85: an SDK review rides the CLI's preset instead of replacing its prompt."""

    @pytest.mark.asyncio
    async def test_sdk_review_sets_default_system_prompt_flag(self) -> None:
        template = _make_template()
        mock_provider = _make_mock_provider(can_read_files=True)

        with (
            patch(f"{_P}.get_profile") as mock_get_profile,
            patch(f"{_P}.get_provider", return_value=mock_provider),
            patch(f"{_P}.ensure_provider_loaded"),
        ):
            from squadron.providers.base import AuthType, ProfileName, ProviderType
            from squadron.providers.profiles import ProviderProfile

            mock_get_profile.return_value = ProviderProfile(
                name=ProfileName.SDK,
                provider=ProviderType.SDK,
                auth_type=AuthType.SESSION,
            )
            await run_review_with_profile(template, {"input": "file.md"}, profile="sdk")

        config = mock_provider.create_agent.call_args[0][0]
        assert config.use_default_system_prompt is True
        # The template prompt is unchanged — it now rides `append` rather than replacing.
        assert config.instructions is not None
        assert template.system_prompt in config.instructions

    @pytest.mark.asyncio
    async def test_non_sdk_review_leaves_preset_flag_off(self) -> None:
        template = _make_template()
        mock_provider = _make_mock_provider()

        with (
            patch(f"{_P}.get_profile") as mock_get_profile,
            patch(f"{_P}.get_provider", return_value=mock_provider),
            patch(f"{_P}.ensure_provider_loaded"),
        ):
            from squadron.providers.profiles import ProviderProfile

            mock_get_profile.return_value = ProviderProfile(
                name="openai",
                provider="openai",
                api_key_env="OPENAI_API_KEY",
            )
            await run_review_with_profile(
                template, {"input": "file.md"}, profile="openai", model="gpt-4o"
            )

        config = mock_provider.create_agent.call_args[0][0]
        assert config.use_default_system_prompt is False
        assert config.instructions is not None

    @staticmethod
    async def _run_sdk(override: list[str] | None = None) -> object:
        from squadron.providers.base import AuthType, ProfileName, ProviderType
        from squadron.providers.profiles import ProviderProfile

        template = _make_template()
        template.setting_sources = ["project"]
        with (
            patch(f"{_P}.get_profile") as mock_get_profile,
            patch(f"{_P}.get_provider", return_value=_make_mock_provider(can_read_files=True)),
            patch(f"{_P}.ensure_provider_loaded"),
        ):
            mock_get_profile.return_value = ProviderProfile(
                name=ProfileName.SDK,
                provider=ProviderType.SDK,
                auth_type=AuthType.SESSION,
            )
            return await run_review_with_profile(
                template, {"input": "file.md"}, profile="sdk", setting_sources_override=override
            )

    @pytest.mark.asyncio
    async def test_sdk_review_records_preset_append_and_project(self) -> None:
        """Slice 932 D12: recorded at every verbosity, from the config actually sent."""
        result = await self._run_sdk()

        assert result.system_prompt_mode == "preset+append"  # type: ignore[attr-defined]
        assert result.setting_sources == "project"  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_pr_review_override_records_none(self) -> None:
        result = await self._run_sdk(override=[])

        assert result.setting_sources == "none"  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_non_sdk_review_records_custom_and_non_sdk(self) -> None:
        template = _make_template()
        mock_provider = _make_mock_provider()

        with (
            patch(f"{_P}.get_profile") as mock_get_profile,
            patch(f"{_P}.get_provider", return_value=mock_provider),
            patch(f"{_P}.ensure_provider_loaded"),
        ):
            from squadron.providers.profiles import ProviderProfile

            mock_get_profile.return_value = ProviderProfile(
                name="openai",
                provider="openai",
                api_key_env="OPENAI_API_KEY",
            )
            result = await run_review_with_profile(
                template, {"input": "file.md"}, profile="openai", model="gpt-4o"
            )

        assert result.system_prompt_mode == "custom"
        assert result.setting_sources == "n/a (non-SDK)"


# The tail of a real minimax-m3 reply (925 code review, 20260922): the model wrote its own
# tool-call markup as text and the turn ended with a clean stop, so no review was emitted.
_TEXT_TOOL_CALL_REPLY = (
    "Let me verify it doesn't use `$ARGUMENTS`:]<]minimax[>[<tool_call>\n"
    ']<]minimax[>[<invoke name="read_file">]<]minimax[>[<path>commands/agents/sq-analysis/'
    "SKILL.md]<]minimax[>[</path>]<]minimax[>[</invoke>"
)


class TestRecoveryTurn:
    """#92: a reply that ends mid-task gets exactly one follow-up on the same agent."""

    def _scripted_provider(
        self,
        replies: list[str | EmptyFinalTurnError],
        metadata: list[dict[str, object]] | None = None,
    ) -> tuple[MagicMock, list[str]]:
        """Each reply is text to yield, or an ``EmptyFinalTurnError`` to raise."""
        sent: list[str] = []
        agent = MagicMock()
        agent.state = AgentState.idle
        agent.shutdown = AsyncMock()

        async def _handle(message: Message) -> AsyncIterator[Message]:
            turn = len(sent)
            sent.append(message.content)
            reply = replies[turn]
            if isinstance(reply, EmptyFinalTurnError):
                raise reply
            yield Message(
                sender="mock-agent",
                recipients=[],
                content=reply,
                message_type=MessageType.chat,
                metadata=(metadata or [{}] * len(replies))[turn],
            )

        agent.handle_message = _handle
        provider = MagicMock()
        provider.capabilities = ProviderCapabilities(can_read_files=False, applies_output_budget=True)
        provider.create_agent = AsyncMock(return_value=agent)
        return provider, sent

    async def _run(self, provider: MagicMock, max_output_tokens: int | None = None) -> ReviewResult:
        from squadron.providers.profiles import ProviderProfile

        with (
            patch(f"{_P}.get_profile") as mock_get_profile,
            patch(f"{_P}.get_provider", return_value=provider),
            patch(f"{_P}.ensure_provider_loaded"),
        ):
            mock_get_profile.return_value = ProviderProfile(
                name="openai", provider="openai", api_key_env="OPENAI_API_KEY"
            )
            return await run_review_with_profile(
                _make_template(),
                {"input": "file.md"},
                profile="openai",
                max_output_tokens=max_output_tokens,
            )

    @pytest.mark.asyncio
    async def test_text_tool_call_reply_is_recovered(self, caplog: pytest.LogCaptureFixture) -> None:
        from squadron.review.models import Verdict
        from squadron.review.turn_capture import FINISH_REVIEW_PROMPT

        provider, sent = self._scripted_provider(
            [_TEXT_TOOL_CALL_REPLY, _SAMPLE_REVIEW_OUTPUT],
            [
                {"tools_given": ["read_file"], "tool_calls_made": 29, "stop_reason": "stop"},
                {"tools_given": ["read_file"], "tool_calls_made": 2, "stop_reason": "stop"},
            ],
        )
        with caplog.at_level(logging.WARNING, logger="squadron.review.review_client"):
            result = await self._run(provider)

        assert result.verdict is Verdict.PASS
        assert result.findings
        assert result.recovery_turn_used is True
        assert sent[1] == FINISH_REVIEW_PROMPT
        # Per-turn counts sum; the model did 31 calls' worth of reading in total.
        assert result.tool_calls_made == 31
        assert any(
            "ended its turn without writing the review" in r.getMessage() for r in caplog.records
        )

    @pytest.mark.asyncio
    async def test_clean_reply_sends_no_follow_up(self) -> None:
        provider, sent = self._scripted_provider([_SAMPLE_REVIEW_OUTPUT])

        result = await self._run(provider)

        assert len(sent) == 1
        assert result.recovery_turn_used is False

    @pytest.mark.asyncio
    async def test_recovery_is_bounded_to_one_turn(self) -> None:
        """A follow-up that also ends mid-task stays UNKNOWN; nothing loops."""
        from squadron.review.models import Verdict

        provider, sent = self._scripted_provider(
            [_TEXT_TOOL_CALL_REPLY, "Let me write the findings now."]
        )

        result = await self._run(provider)

        assert len(sent) == 2
        assert result.verdict is Verdict.UNKNOWN
        assert result.recovery_turn_used is True
        # Both replies are kept, so the degraded artifact shows what each turn said.
        assert "<tool_call>" in result.raw_output
        assert "Let me write the findings now." in result.raw_output

    @pytest.mark.asyncio
    @pytest.mark.parametrize("stop_reason", ["length", "max_tokens"])
    async def test_spent_budget_skips_recovery(
        self, stop_reason: str, caplog: pytest.LogCaptureFixture
    ) -> None:
        """D2: a turn that ran out of output budget would run out again."""
        from squadron.review.models import Verdict

        provider, sent = self._scripted_provider(
            [_TEXT_TOOL_CALL_REPLY, _SAMPLE_REVIEW_OUTPUT], [{"stop_reason": stop_reason}, {}]
        )
        with caplog.at_level(logging.WARNING, logger="squadron.review.review_client"):
            result = await self._run(provider)

        assert len(sent) == 1
        assert result.verdict is Verdict.UNKNOWN
        assert result.recovery_turn_used is False
        assert result.output_budget_exhausted is True
        messages = [r.getMessage() for r in caplog.records]
        assert any(f"stop reason: {stop_reason}" in m and "backend default" in m for m in messages)
        assert not any("asking once more" in m for m in messages)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("stop_reason", [None, "stop", "end_turn"])
    async def test_non_budget_stop_reason_still_recovers(self, stop_reason: str | None) -> None:
        first: dict[str, object] = {} if stop_reason is None else {"stop_reason": stop_reason}
        provider, sent = self._scripted_provider(
            [_TEXT_TOOL_CALL_REPLY, _SAMPLE_REVIEW_OUTPUT], [first, {}]
        )

        result = await self._run(provider)

        assert len(sent) == 2
        assert result.recovery_turn_used is True
        assert result.output_budget_exhausted is False

    @pytest.mark.asyncio
    async def test_recovery_turn_ending_on_budget_is_reported(self) -> None:
        provider, _ = self._scripted_provider(
            [_TEXT_TOOL_CALL_REPLY, "Let me write the findings now."],
            [{"stop_reason": "stop"}, {"stop_reason": "length"}],
        )

        result = await self._run(provider)

        assert result.recovery_turn_used is True
        assert result.output_budget_exhausted is True

    @pytest.mark.asyncio
    async def test_recovery_turn_keeps_the_same_agent_and_tools(self) -> None:
        """D3: the follow-up may still need to read, so it keeps its tools."""
        provider, sent = self._scripted_provider([_TEXT_TOOL_CALL_REPLY, _SAMPLE_REVIEW_OUTPUT])
        agent = provider.create_agent.return_value
        agent.tools = ["read_file", "grep"]
        seen: list[tuple[int, list[str]]] = []
        scripted = agent.handle_message

        async def _recording(message: Message) -> AsyncIterator[Message]:
            seen.append((id(agent), list(agent.tools)))
            async for response in scripted(message):
                yield response

        agent.handle_message = _recording

        await self._run(provider)

        assert len(sent) == 2
        provider.create_agent.assert_awaited_once()
        assert seen[0] == seen[1]


def _empty_turn(finish_reason: str | None = "stop") -> EmptyFinalTurnError:
    return EmptyFinalTurnError(
        f"Model returned an empty final turn (finish_reason={finish_reason!r}, "
        "reasoning_chars=1022); no response to deliver.",
        finish_reason=finish_reason,
        reasoning_chars=1022,
        tool_calls_made=3,
        failed_tool_calls=0,
    )


class TestEmptyFinalTurnRecovery:
    """Slice 924 D7: reasoning with no reply gets the same single recovery turn."""

    _scripted_provider = TestRecoveryTurn._scripted_provider  # pyright: ignore[reportPrivateUsage]
    _run = TestRecoveryTurn._run  # pyright: ignore[reportPrivateUsage]

    @pytest.mark.asyncio
    async def test_empty_first_turn_is_recovered_with_summed_telemetry(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        from squadron.review.models import Verdict
        from squadron.review.turn_capture import FINISH_REVIEW_PROMPT

        provider, sent = self._scripted_provider(
            [_empty_turn(), _SAMPLE_REVIEW_OUTPUT],
            [
                {},
                {
                    "tools_given": ["read_file"],
                    "tool_calls_made": 2,
                    "stop_reason": "end_turn",
                    "reasoning_chars": 100,
                },
            ],
        )
        with caplog.at_level(logging.WARNING, logger="squadron.review.review_client"):
            result = await self._run(provider)

        assert result.verdict is Verdict.PASS
        assert result.recovery_turn_used is True
        assert sent[1] == FINISH_REVIEW_PROMPT
        assert result.stop_reason == "end_turn"
        assert result.tool_calls_made == 5
        assert result.reasoning_chars == 1122
        assert result.failed_tool_calls == 0
        assert any(
            "returned an empty final turn (stop reason: stop, reasoning chars: 1022); "
            "asking once more" in r.getMessage()
            for r in caplog.records
        )

    @pytest.mark.asyncio
    async def test_empty_first_turn_on_a_spent_budget_reraises(self) -> None:
        error = _empty_turn("length")
        provider, sent = self._scripted_provider([error, _SAMPLE_REVIEW_OUTPUT])

        with pytest.raises(EmptyFinalTurnError) as exc_info:
            await self._run(provider)

        assert exc_info.value is error
        assert len(sent) == 1

    @pytest.mark.asyncio
    async def test_empty_recovery_turn_propagates(self) -> None:
        second = _empty_turn()
        provider, sent = self._scripted_provider([_empty_turn(), second])

        with pytest.raises(EmptyFinalTurnError) as exc_info:
            await self._run(provider)

        assert exc_info.value is second
        assert len(sent) == 2
        provider.create_agent.return_value.shutdown.assert_awaited_once()


class TestOutputBudgetThreading:
    """Slice 924 B.10: the budget reaches AgentConfig and the result."""

    _scripted_provider = TestRecoveryTurn._scripted_provider  # pyright: ignore[reportPrivateUsage]
    _run = TestRecoveryTurn._run  # pyright: ignore[reportPrivateUsage]

    @pytest.mark.asyncio
    async def test_budget_reaches_agent_config_and_result(self) -> None:
        provider, _ = self._scripted_provider([_SAMPLE_REVIEW_OUTPUT])

        result = await self._run(provider, max_output_tokens=32000)

        config: AgentConfig = provider.create_agent.call_args.args[0]
        assert config.max_output_tokens == 32000
        assert result.max_output_tokens == 32000

    @pytest.mark.asyncio
    async def test_no_budget_leaves_both_none(self) -> None:
        provider, _ = self._scripted_provider([_SAMPLE_REVIEW_OUTPUT])

        result = await self._run(provider)

        assert provider.create_agent.call_args.args[0].max_output_tokens is None
        assert result.max_output_tokens is None

    @pytest.mark.asyncio
    async def test_skip_warning_names_the_sent_budget(self, caplog: pytest.LogCaptureFixture) -> None:
        provider, _ = self._scripted_provider([_TEXT_TOOL_CALL_REPLY], [{"stop_reason": "length"}])
        with caplog.at_level(logging.WARNING, logger="squadron.review.review_client"):
            await self._run(provider, max_output_tokens=256)

        assert any("budget: 256 tokens" in r.getMessage() for r in caplog.records)

    @pytest.mark.asyncio
    async def test_provider_that_cannot_send_a_budget_records_none(self) -> None:
        """The agent still gets the budget (so it can warn), but the artifact won't claim it."""
        provider, _ = self._scripted_provider([_SAMPLE_REVIEW_OUTPUT])
        provider.capabilities = ProviderCapabilities(can_read_files=False)

        result = await self._run(provider, max_output_tokens=4096)

        assert provider.create_agent.call_args.args[0].max_output_tokens == 4096
        assert result.max_output_tokens is None


class TestRunCost:
    """Slice 931 D8, D9: turns, usage, and wall-clock land on the result or the error."""

    async def _run(self, provider_type: str, agent: MagicMock, *, clock: list[float]) -> ReviewResult:
        from squadron.providers.profiles import ProviderProfile

        provider = _make_mock_provider(agent=agent)
        with (
            patch(f"{_P}.get_profile") as mock_get_profile,
            patch(f"{_P}.get_provider", return_value=provider),
            patch(f"{_P}.ensure_provider_loaded"),
            patch(f"{_P}.time.monotonic", side_effect=clock),
        ):
            mock_get_profile.return_value = ProviderProfile(name="p", provider=provider_type)
            return await run_review_with_profile(_make_template(), {"input": "file.md"}, profile="p")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("provider_type", ["openai", "sdk", "openai_oauth"])
    async def test_duration_is_stamped_for_every_provider(self, provider_type: str) -> None:
        result = await self._run(provider_type, _make_mock_agent(), clock=[100.0, 103.5])

        assert result.duration_seconds == pytest.approx(3.5)

    @pytest.mark.asyncio
    async def test_stamped_turns_and_usage_land_on_result(self) -> None:
        from squadron.core.usage import TokenUsage

        agent = MagicMock()
        agent.shutdown = AsyncMock()

        async def _handle(message: Message) -> AsyncIterator[Message]:
            yield Message(
                sender="a",
                recipients=[],
                content=_SAMPLE_REVIEW_OUTPUT,
                message_type=MessageType.chat,
                metadata={"turns": 4, "usage": TokenUsage(prompt=100, completion=9)},
            )

        agent.handle_message = _handle

        result = await self._run("openai", agent, clock=[0.0, 1.0])

        assert result.turns == 4
        assert result.usage == TokenUsage(prompt=100, completion=9)

    @pytest.mark.asyncio
    async def test_provider_error_leaves_with_duration_and_is_the_same_object(self) -> None:
        from squadron.providers.errors import ProviderAPIError

        raised = ProviderAPIError("boom", status_code=500)
        agent = MagicMock()
        agent.shutdown = AsyncMock()

        async def _handle(message: Message) -> AsyncIterator[Message]:
            raise raised
            yield  # pragma: no cover - makes this an async generator

        agent.handle_message = _handle

        with pytest.raises(ProviderAPIError) as exc_info:
            await self._run("openai", agent, clock=[10.0, 12.25])

        assert exc_info.value is raised
        assert raised.duration_seconds == pytest.approx(2.25)
        agent.shutdown.assert_awaited_once()


class TestEffortThreading:
    """Slice 931 D4: effort reaches AgentConfig; the result records it only if sent."""

    _scripted_provider = TestRecoveryTurn._scripted_provider  # pyright: ignore[reportPrivateUsage]

    async def _run(self, provider: MagicMock, effort: Effort | None) -> ReviewResult:
        from squadron.providers.profiles import ProviderProfile

        with (
            patch(f"{_P}.get_profile") as mock_get_profile,
            patch(f"{_P}.get_provider", return_value=provider),
            patch(f"{_P}.ensure_provider_loaded"),
        ):
            mock_get_profile.return_value = ProviderProfile(name="p", provider="openai")
            return await run_review_with_profile(
                _make_template(), {"input": "file.md"}, profile="p", effort=effort
            )

    @pytest.mark.asyncio
    async def test_applied_effort_reaches_config_and_result(self) -> None:
        provider, _ = self._scripted_provider([_SAMPLE_REVIEW_OUTPUT])
        provider.capabilities = ProviderCapabilities(applies_effort=True)

        result = await self._run(provider, Effort.low)

        assert provider.create_agent.call_args.args[0].effort is Effort.low
        assert result.effort is Effort.low

    @pytest.mark.asyncio
    async def test_provider_that_cannot_apply_effort_records_none(self) -> None:
        """The agent still gets it (so it can warn), but the artifact won't claim it."""
        provider, _ = self._scripted_provider([_SAMPLE_REVIEW_OUTPUT])
        provider.capabilities = ProviderCapabilities(applies_effort=False)

        result = await self._run(provider, Effort.high)

        assert provider.create_agent.call_args.args[0].effort is Effort.high
        assert result.effort is None

    @pytest.mark.asyncio
    async def test_no_effort_leaves_both_none(self) -> None:
        provider, _ = self._scripted_provider([_SAMPLE_REVIEW_OUTPUT])
        provider.capabilities = ProviderCapabilities(applies_effort=True)

        result = await self._run(provider, None)

        assert provider.create_agent.call_args.args[0].effort is None
        assert result.effort is None

    @pytest.mark.asyncio
    async def test_codex_artifact_records_effort(self) -> None:
        """Slice 129 D5: Codex applies effort, so its artifact records it."""
        from squadron.providers.codex.provider import CodexProvider
        from squadron.review.persistence import format_review_markdown

        provider, _ = self._scripted_provider([_SAMPLE_REVIEW_OUTPUT])
        provider.capabilities = CodexProvider().capabilities

        result = await self._run(provider, Effort.low)
        md = format_review_markdown(result, "code")
        frontmatter = md.split("---")[1]

        assert result.effort is Effort.low
        assert "effort: low" in frontmatter
        assert "- Effort: low" in md


class TestDocsRootNote:
    """A file-reading model is told where cf document paths resolve."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("can_read_files", "has_docs_root", "expect_note"),
        [
            (True, True, True),
            (True, False, False),
            (False, True, False),
        ],
    )
    async def test_note_only_for_file_readers_in_a_cf_project(
        self, tmp_path: Path, can_read_files: bool, has_docs_root: bool, expect_note: bool
    ) -> None:
        from squadron.integrations.context_forge import DOCS_ROOT
        from squadron.providers.profiles import ProviderProfile

        (tmp_path / "file.md").write_text("doc")
        if has_docs_root:
            (tmp_path / DOCS_ROOT).mkdir()
        with (
            patch(f"{_P}.get_profile") as mock_get_profile,
            patch(
                f"{_P}.get_provider", return_value=_make_mock_provider(can_read_files=can_read_files)
            ),
            patch(f"{_P}.ensure_provider_loaded"),
        ):
            mock_get_profile.return_value = ProviderProfile(
                name="openai", provider="openai", api_key_env="OPENAI_API_KEY"
            )
            result = await run_review_with_profile(
                _make_template(model="test-model"),
                {"input": "file.md", "cwd": str(tmp_path)},
                profile="openai",
                model="test-model",
                verbosity=2,
            )

        assert result.system_prompt is not None
        assert (f"relative to `{DOCS_ROOT}/`" in result.system_prompt) is expect_note
