"""Tests for AgentConfig.convention_root and its threading through run_review_with_profile.

Slice 382, design D1: a PR review's scratch worktree holds the code under review, but
conventions (CLAUDE.md) must still come from the trusted checkout. convention_root lets a
caller separate "where code lives" (cwd) from "where conventions live" (convention_root)
without changing behavior for any caller that omits it.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadron.core.models import AgentState, Message, MessageType
from squadron.providers.base import ProviderCapabilities
from squadron.providers.profiles import ProviderProfile
from squadron.review.review_client import _inject_file_contents, run_review_with_profile
from squadron.review.templates import InputDef, ReviewTemplate

# ---------------------------------------------------------------------------
# _inject_file_contents: convention_root overrides CLAUDE.md source directly
# ---------------------------------------------------------------------------


def test_convention_root_overrides_claude_md_source(tmp_path: Path) -> None:
    """CLAUDE.md is read from convention_root, not inputs['cwd'], when given."""
    cwd_dir = tmp_path / "worktree"
    cwd_dir.mkdir()
    (cwd_dir / "CLAUDE.md").write_text("# Worktree conventions\nUntrusted content.")

    convention_dir = tmp_path / "checkout"
    convention_dir.mkdir()
    (convention_dir / "CLAUDE.md").write_text("# Checkout conventions\nTrusted content.")

    inputs = {"cwd": str(cwd_dir)}
    result = _inject_file_contents("Review", inputs, convention_root=str(convention_dir))

    assert "Trusted content." in result
    assert "Untrusted content." not in result


def test_convention_root_omitted_reads_from_cwd_byte_identical(tmp_path: Path) -> None:
    """Omitting convention_root preserves today's cwd-sourced behavior exactly.

    Pinned against the same fixture shape as
    test_content_injection.py::test_claude_md_injected_when_present so a regression in
    either path is caught by both files.
    """
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("# Project conventions\nNo magic defaults.")

    prompt = "Review code"
    inputs = {"cwd": str(tmp_path)}

    with_default = _inject_file_contents(prompt, inputs)
    without_param = _inject_file_contents(prompt, inputs, convention_root=None)

    assert with_default == without_param
    assert "CLAUDE.md (project conventions)" in with_default
    assert "No magic defaults." in with_default


# ---------------------------------------------------------------------------
# run_review_with_profile: convention_root threads through to the prompt
# ---------------------------------------------------------------------------


def _make_template() -> ReviewTemplate:
    return ReviewTemplate(
        name="tasks",
        description="Test template",
        system_prompt="You are a reviewer.",
        allowed_tools=[],
        permission_mode="bypassPermissions",
        setting_sources=None,
        required_inputs=[
            InputDef(name="input", description="doc"),
            InputDef(name="against", description="ref"),
        ],
        optional_inputs=[
            InputDef(name="cwd", description="dir", default="."),
        ],
        prompt_template="Review {input} against {against}",
        profile=None,
        model=None,
    )


async def _run_with_mocked_provider(
    template: ReviewTemplate, inputs: dict[str, str], *, convention_root: str | None
) -> list[str]:
    """Run run_review_with_profile against a stubbed non-SDK provider, return captured prompts."""
    captured_prompts: list[str] = []
    review_output = "## Summary\nPASS\n\n## Findings\n\n### [PASS] Coverage\nAll tasks covered."

    mock_agent = MagicMock()
    mock_agent.state = AgentState.idle
    mock_agent.shutdown = AsyncMock()

    async def capture_handle(message: Message) -> AsyncIterator[Message]:
        captured_prompts.append(message.content)
        yield Message(
            sender="mock",
            recipients=[],
            content=review_output,
            message_type=MessageType.chat,
        )

    mock_agent.handle_message = capture_handle

    mock_provider = MagicMock()
    mock_provider.capabilities = ProviderCapabilities(can_read_files=False)
    mock_provider.create_agent = AsyncMock(return_value=mock_agent)

    with (
        patch(
            "squadron.review.review_client.get_profile",
            return_value=ProviderProfile(
                name="openai",
                provider="openai",
                api_key_env="OPENAI_API_KEY",
            ),
        ),
        patch("squadron.review.review_client.get_provider", return_value=mock_provider),
        patch("squadron.review.review_client.ensure_provider_loaded"),
    ):
        await run_review_with_profile(
            template,
            inputs,
            profile="openai",
            model="gpt-4o",
            convention_root=convention_root,
        )

    return captured_prompts


@pytest.mark.asyncio
async def test_run_review_with_profile_honors_convention_root(tmp_path: Path) -> None:
    task_file = tmp_path / "tasks.md"
    task_file.write_text("# Tasks\n- [ ] Implement feature X")
    design_file = tmp_path / "design.md"
    design_file.write_text("# Design\nFeature X overview")

    cwd_dir = tmp_path / "worktree"
    cwd_dir.mkdir()
    (cwd_dir / "CLAUDE.md").write_text("# Worktree conventions\nUntrusted content.")

    convention_dir = tmp_path / "checkout"
    convention_dir.mkdir()
    (convention_dir / "CLAUDE.md").write_text("# Checkout conventions\nTrusted content.")

    inputs = {
        "input": str(task_file),
        "against": str(design_file),
        "cwd": str(cwd_dir),
    }

    captured_prompts = await _run_with_mocked_provider(
        _make_template(), inputs, convention_root=str(convention_dir)
    )

    assert len(captured_prompts) == 1
    assert "Trusted content." in captured_prompts[0]
    assert "Untrusted content." not in captured_prompts[0]


@pytest.mark.asyncio
async def test_run_review_with_profile_without_convention_root_is_byte_identical(
    tmp_path: Path,
) -> None:
    """Every existing caller (e.g. sq review code) omits convention_root and is unaffected."""
    task_file = tmp_path / "tasks.md"
    task_file.write_text("# Tasks\n- [ ] Implement feature X")
    design_file = tmp_path / "design.md"
    design_file.write_text("# Design\nFeature X overview")

    (tmp_path / "CLAUDE.md").write_text("# Project conventions\nNo magic defaults.")

    inputs = {
        "input": str(task_file),
        "against": str(design_file),
        "cwd": str(tmp_path),
    }

    prompts_default = await _run_with_mocked_provider(_make_template(), inputs, convention_root=None)

    # Re-run without passing the parameter at all (its true default), same provider stub.
    mock_agent = MagicMock()
    mock_agent.state = AgentState.idle
    mock_agent.shutdown = AsyncMock()
    captured_no_param: list[str] = []

    async def capture_handle(message: Message) -> AsyncIterator[Message]:
        captured_no_param.append(message.content)
        yield Message(
            sender="mock",
            recipients=[],
            content="## Summary\nPASS\n\n## Findings\n\n### [PASS] Coverage\nAll covered.",
            message_type=MessageType.chat,
        )

    mock_agent.handle_message = capture_handle
    mock_provider = MagicMock()
    mock_provider.capabilities = ProviderCapabilities(can_read_files=False)
    mock_provider.create_agent = AsyncMock(return_value=mock_agent)

    with (
        patch(
            "squadron.review.review_client.get_profile",
            return_value=ProviderProfile(
                name="openai", provider="openai", api_key_env="OPENAI_API_KEY"
            ),
        ),
        patch("squadron.review.review_client.get_provider", return_value=mock_provider),
        patch("squadron.review.review_client.ensure_provider_loaded"),
    ):
        await run_review_with_profile(_make_template(), inputs, profile="openai", model="gpt-4o")

    assert captured_no_param[0] == prompts_default[0]
    assert "No magic defaults." in prompts_default[0]
