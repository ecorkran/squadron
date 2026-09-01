"""End-to-end non-SDK review with a real tool call (slice 265, SC6, issue #68).

Exercises the whole path — run_review_with_profile -> AgentConfig -> OpenAICompatibleAgent
-> squadron tool registry -> the filesystem -> the review parser — with only the OpenAI
network client mocked. Before this slice the migrated template's names were dropped by the
registry lookup and the review ran tool-less while still reporting a verdict; the assertion
that matters is that the mocked read actually happened AND the parsed result is unchanged in
shape from a tool-less review.

Follows the mocking approach already used in tests/providers/openai and
tests/pipeline/test_dispatch_tools.py — no second pattern invented here.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadron.review.models import Verdict
from squadron.review.review_client import run_review_with_profile
from squadron.review.templates import get_template, load_all_templates
from tests.providers.openai.conftest import text_chunk, tool_chunk

_P = "squadron.review.review_client"
_PROVIDER_MODULE = "squadron.providers.openai.provider"

_TARGET_NAME = "target.py"
_TARGET_BODY = "def divide(a, b):\n    return a / b\n"

_REVIEW_OUTPUT = """\
## Summary
CONCERNS

## Findings

### [CONCERN] Unguarded division
location: target.py:2
`divide` does not guard against a zero divisor.
"""


async def _stream(chunks: list[Any]) -> AsyncIterator[Any]:
    for chunk in chunks:
        yield chunk


def _openrouter_profile() -> object:
    from squadron.providers.profiles import ProviderProfile

    return ProviderProfile(
        name="openrouter",
        provider="openai",
        base_url="https://openrouter.ai/api/v1",
        api_key_env="OPENROUTER_API_KEY",
        description="test",
    )


def _two_turn_client(read_path: str) -> MagicMock:
    """Turn one calls read_file; turn two returns a parseable review."""
    read_args = json.dumps({"path": read_path})
    client = MagicMock()
    client.close = AsyncMock()
    client.chat.completions.create = AsyncMock(
        side_effect=[
            _stream([tool_chunk(0, "call-1", "read_file", read_args)]),
            _stream([text_chunk(_REVIEW_OUTPUT)]),
        ]
    )
    return client


def _tool_less_client() -> MagicMock:
    client = MagicMock()
    client.close = AsyncMock()
    client.chat.completions.create = AsyncMock(return_value=_stream([text_chunk(_REVIEW_OUTPUT)]))
    return client


@pytest.mark.asyncio
async def test_non_sdk_review_executes_tool_call_and_parses_normally(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    target = tmp_path / _TARGET_NAME
    target.write_text(_TARGET_BODY)

    load_all_templates()
    template = get_template("code")
    assert template is not None

    client = _two_turn_client(_TARGET_NAME)
    with (
        patch(f"{_P}.get_profile", return_value=_openrouter_profile()),
        patch(f"{_PROVIDER_MODULE}.AsyncOpenAI", return_value=client),
    ):
        result = await run_review_with_profile(
            template,
            {"cwd": str(tmp_path), "files": str(target)},
            profile="openrouter",
            model="moonshotai/kimi-k2",
        )

    # The model actually got a second turn, which only happens if turn one's tool call was
    # executed and its result appended to history.
    assert client.chat.completions.create.call_count == 2

    # The tool really ran against the real file: the request history carries the file body
    # back to the model, which a dropped tool name could never produce.
    history_messages = client.chat.completions.create.call_args_list[1].kwargs["messages"]
    tool_results = [m for m in history_messages if m.get("role") == "tool"]
    assert len(tool_results) == 1
    assert _TARGET_BODY in tool_results[0]["content"]

    # SC6: the parsed result is unchanged in shape from a tool-less review.
    assert result.verdict is Verdict.CONCERNS
    assert len(result.findings) == 1
    assert result.findings[0].title == "Unguarded division"

    # Telemetry rode along.
    assert result.tools_given == ["read_file", "list_files", "grep"]
    assert result.tool_calls_made == 1


@pytest.mark.asyncio
async def test_tool_using_and_tool_less_reviews_parse_identically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SC6's "unchanged in shape" half, asserted by direct comparison."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    (tmp_path / _TARGET_NAME).write_text(_TARGET_BODY)

    load_all_templates()
    template = get_template("code")
    assert template is not None
    inputs = {"cwd": str(tmp_path)}

    with (
        patch(f"{_P}.get_profile", return_value=_openrouter_profile()),
        patch(f"{_PROVIDER_MODULE}.AsyncOpenAI", return_value=_two_turn_client(_TARGET_NAME)),
    ):
        with_tools = await run_review_with_profile(
            template, dict(inputs), profile="openrouter", model="moonshotai/kimi-k2"
        )

    with (
        patch(f"{_P}.get_profile", return_value=_openrouter_profile()),
        patch(f"{_PROVIDER_MODULE}.AsyncOpenAI", return_value=_tool_less_client()),
    ):
        without_tools = await run_review_with_profile(
            template,
            dict(inputs),
            profile="openrouter",
            model="moonshotai/kimi-k2",
            allowed_tools=[],
        )

    assert with_tools.verdict == without_tools.verdict
    assert [f.title for f in with_tools.findings] == [f.title for f in without_tools.findings]
    assert [f.severity for f in with_tools.findings] == [f.severity for f in without_tools.findings]
    # The telemetry is the one intended difference.
    assert with_tools.tool_calls_made == 1
    assert without_tools.tools_given is None
