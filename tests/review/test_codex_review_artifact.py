"""Codex effort and usage reach the review artifact (slice 129, Tasks 8–9 end to end).

Drives ``run_review_with_profile`` with the real ``CodexProvider`` and agent over the
fake ``openai_codex`` SDK, then renders the artifact with ``format_review_markdown``.
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest

from squadron.core.models import Effort
from squadron.core.usage import TokenUsage
from squadron.providers.codex.provider import CodexProvider
from squadron.providers.profiles import ProviderProfile
from squadron.review.models import ReviewResult
from squadron.review.persistence import format_review_markdown
from squadron.review.review_client import run_review_with_profile
from squadron.review.run_cost import NOT_COMPUTED
from squadron.review.templates import ReviewTemplate
from tests.providers.codex.fake_sdk import (
    FakeSdk,
    ThreadTokenUsage,
    TurnResult,
    Usage,
    installed_fake_sdk,
)

_P = "squadron.review.review_client"

_REVIEW_OUTPUT = """\
**Verdict:** PASS

## Findings

### [PASS] — Code quality is good

The code follows best practices.
"""


@pytest.fixture()
def codex_sdk() -> Generator[FakeSdk]:
    """Fake SDK plus a logged-in per-test home, so CodexProvider.create_agent succeeds."""
    auth_file = Path.home() / ".codex" / "auth.json"
    auth_file.parent.mkdir(parents=True, exist_ok=True)
    auth_file.write_text("{}")
    with installed_fake_sdk() as sdk:
        yield sdk


def _template() -> ReviewTemplate:
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
    )


async def _review(effort: Effort | None) -> ReviewResult:
    """One review through CodexProvider, as the codex-agent alias (effort from the alias)."""
    with (
        patch(
            f"{_P}.get_profile",
            return_value=ProviderProfile(name="openai-oauth", provider="openai-oauth"),
        ),
        patch(f"{_P}.get_provider", return_value=CodexProvider()),
        patch(f"{_P}.ensure_provider_loaded"),
    ):
        return await run_review_with_profile(
            _template(),
            {"input": "file.md"},
            profile="openai-oauth",
            model="gpt-5.3-codex",
            effort=effort,
        )


@pytest.mark.asyncio
async def test_effort_and_usage_reach_the_artifact(codex_sdk: FakeSdk) -> None:
    codex_sdk.turn.run.return_value = TurnResult(
        final_response=_REVIEW_OUTPUT,
        usage=ThreadTokenUsage(
            last=Usage(
                input_tokens=1200,
                cached_input_tokens=300,
                output_tokens=450,
                reasoning_output_tokens=90,
            )
        ),
    )

    result = await _review(Effort.high)

    assert codex_sdk.thread.turn.call_args.kwargs["effort"].value == "high"
    assert result.effort is Effort.high
    assert result.usage == TokenUsage(prompt=1200, cached=300, completion=450, reasoning=90)
    md = format_review_markdown(result, "code")
    frontmatter = md.split("---")[1]
    assert "effort: high" in frontmatter
    assert "promptTokens: 1200" in frontmatter
    assert "reasoningTokens: 90" in frontmatter
    assert "- Effort: high" in md
    assert "- Tokens — prompt / cached / completion / reasoning: 1200 / 300 / 450 / 90" in md


@pytest.mark.asyncio
async def test_turn_without_usage_persists_no_figures(codex_sdk: FakeSdk) -> None:
    codex_sdk.turn.run.return_value = TurnResult(final_response=_REVIEW_OUTPUT, usage=None)

    result = await _review(Effort.high)

    assert not result.usage.reported
    md = format_review_markdown(result, "code")
    frontmatter = md.split("---")[1]
    for key in ("promptTokens", "cachedTokens", "completionTokens", "reasoningTokens"):
        assert key not in frontmatter
    unreported = " / ".join([NOT_COMPUTED] * 4)
    assert f"- Tokens — prompt / cached / completion / reasoning: {unreported}" in md
