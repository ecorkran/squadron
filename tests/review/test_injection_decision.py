"""Tests for the run-scoped file-body injection decision (slice 265, design D1).

The decision used to read ``ProviderCapabilities.can_read_files`` alone — a per-provider
constant blind to what a given run was actually given. These tests cover the helper directly
and, end to end, assert what reaches the model's prompt.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadron.core.models import AgentState, Message, MessageType
from squadron.providers.base import AuthType, ProfileName, ProviderCapabilities, ProviderType
from squadron.providers.profiles import ProviderProfile
from squadron.review.review_client import run_review_with_profile
from squadron.review.templates import ReviewTemplate
from squadron.review.tool_support import effective_tools, should_inject_file_bodies

_P = "squadron.review.review_client"

_SAMPLE_REVIEW_OUTPUT = """\
**Verdict:** PASS

## Findings

### [PASS] — Looks fine

Nothing to report.
"""


# ---------------------------------------------------------------------------
# effective_tools / should_inject_file_bodies — unit level
# ---------------------------------------------------------------------------


def test_effective_tools_filters_unregistered_names_for_non_sdk() -> None:
    assert effective_tools(["read_file", "Read", "grep"], "openai") == ["read_file", "grep"]


def test_effective_tools_passes_sdk_names_through_untouched() -> None:
    # SDK profiles resolve their own vocabulary at the config edge, so nothing is filtered.
    assert effective_tools(["Read", "Glob"], ProviderType.SDK) == ["Read", "Glob"]


def test_effective_tools_empty_for_no_declaration() -> None:
    assert effective_tools(None, "openai") == []
    assert effective_tools([], "openai") == []


def test_reader_tool_suppresses_injection() -> None:
    assert (
        should_inject_file_bodies(
            can_read_files=False, allowed_tools=["read_file", "grep"], provider="openai"
        )
        is False
    )


def test_no_reader_tool_still_injects() -> None:
    assert (
        should_inject_file_bodies(can_read_files=False, allowed_tools=["grep"], provider="openai")
        is True
    )


def test_no_tools_declared_still_injects() -> None:
    assert (
        should_inject_file_bodies(can_read_files=False, allowed_tools=None, provider="openai") is True
    )


def test_native_reader_never_injects_regardless_of_tools() -> None:
    for tools in (None, [], ["read_file"], ["Read"]):
        assert (
            should_inject_file_bodies(
                can_read_files=True, allowed_tools=tools, provider=ProviderType.SDK
            )
            is False
        )


def test_unregistered_reader_name_does_not_suppress_injection() -> None:
    # A template still declaring Claude vocabulary against a non-SDK provider has no effective
    # reader, so bodies must still be injected — the pre-migration regression case.
    assert (
        should_inject_file_bodies(can_read_files=False, allowed_tools=["Read"], provider="openai")
        is True
    )


# ---------------------------------------------------------------------------
# End to end — what actually reaches the prompt
# ---------------------------------------------------------------------------


def _make_template(allowed_tools: list[str] | None) -> ReviewTemplate:
    return ReviewTemplate(
        name="test",
        description="Test template",
        system_prompt="You are a reviewer.",
        allowed_tools=allowed_tools,
        permission_mode="bypassPermissions",
        setting_sources=None,
        required_inputs=[],
        optional_inputs=[],
        prompt_template="Review: {input}",
        profile=None,
        model=None,
    )


def _capture_provider(captured: dict[str, str], *, can_read_files: bool) -> MagicMock:
    """A mock provider that records the user prompt its agent receives."""
    agent = MagicMock()
    agent.state = AgentState.idle
    agent.shutdown = AsyncMock()

    async def _handle(message: Message) -> AsyncIterator[Message]:
        captured["prompt"] = message.content
        yield Message(
            sender="mock-agent",
            recipients=[],
            content=_SAMPLE_REVIEW_OUTPUT,
            message_type=MessageType.chat,
        )

    agent.handle_message = _handle
    provider = MagicMock()
    provider.capabilities = ProviderCapabilities(can_read_files=can_read_files)
    provider.create_agent = AsyncMock(return_value=agent)
    return provider


async def _run(tmp_path: Path, *, allowed_tools: list[str] | None, sdk: bool) -> str:
    target = tmp_path / "design.md"
    target.write_text("SENTINEL FILE BODY")
    captured: dict[str, str] = {}
    provider = _capture_provider(captured, can_read_files=sdk)

    if sdk:
        profile = ProviderProfile(
            name=ProfileName.SDK, provider=ProviderType.SDK, auth_type=AuthType.SESSION
        )
    else:
        profile = ProviderProfile(name="openai", provider="openai", api_key_env="OPENAI_API_KEY")

    with (
        patch(f"{_P}.get_profile", return_value=profile),
        patch(f"{_P}.get_provider", return_value=provider),
        patch(f"{_P}.ensure_provider_loaded"),
    ):
        await run_review_with_profile(
            _make_template(allowed_tools),
            {"input": str(target), "cwd": str(tmp_path)},
            profile=profile.name,
        )
    return captured["prompt"]


@pytest.mark.asyncio
async def test_tool_capable_review_skips_file_body_injection(tmp_path: Path) -> None:
    prompt = await _run(tmp_path, allowed_tools=["read_file", "grep"], sdk=False)

    assert "## File Contents" not in prompt
    assert "SENTINEL FILE BODY" not in prompt
    # The prompt still names the file, so the model knows what to read.
    assert "design.md" in prompt


@pytest.mark.asyncio
async def test_no_tools_review_injects_file_bodies_unchanged(tmp_path: Path) -> None:
    prompt = await _run(tmp_path, allowed_tools=None, sdk=False)

    assert "## File Contents" in prompt
    assert "SENTINEL FILE BODY" in prompt


@pytest.mark.asyncio
async def test_unmigrated_template_injects_exactly_as_before(tmp_path: Path) -> None:
    """Byte-identical regression guard: Claude vocabulary on a non-SDK provider is inert."""
    claude_names = await _run(tmp_path, allowed_tools=["Read", "Glob", "Grep"], sdk=False)
    no_tools = await _run(tmp_path, allowed_tools=None, sdk=False)

    assert claude_names == no_tools
    assert "SENTINEL FILE BODY" in claude_names


@pytest.mark.asyncio
async def test_sdk_provider_unaffected_by_effective_tools_change(tmp_path: Path) -> None:
    with_tools = await _run(tmp_path, allowed_tools=["read_file"], sdk=True)
    without_tools = await _run(tmp_path, allowed_tools=None, sdk=True)

    assert "SENTINEL FILE BODY" not in with_tools
    assert "SENTINEL FILE BODY" not in without_tools
    assert with_tools == without_tools
