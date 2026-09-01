"""End-to-end dispatch tool-call integration test (slice 263, task 9).

Exercises the real path — DispatchAction -> one_shot_dispatch -> agent registry ->
OpenAICompatibleAgent -> squadron tool registry -> the filesystem — with only the
OpenAI network client mocked. The assertion that matters is that the file exists
on disk afterward: a mock-call assertion cannot distinguish a real write from the
silent no-op this slice exists to prevent.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadron.pipeline.actions.dispatch import (
    DispatchAction,
    one_shot_dispatch,
    one_shot_dispatch_with_telemetry,
)
from squadron.pipeline.models import ActionContext
from squadron.providers.profiles import ProviderProfile
from tests.providers.openai.conftest import text_chunk, tool_chunk

_TARGET_NAME = "design.md"
_TARGET_CONTENT = "# Design\n\nWritten by the tool call.\n"
_FINAL_TEXT = "Wrote the design file."

_ACTION_MODULE = "squadron.pipeline.actions.dispatch"
_PROVIDER_MODULE = "squadron.providers.openai.provider"


def _openrouter_profile() -> ProviderProfile:
    return ProviderProfile(
        name="openrouter",
        provider="openai",
        base_url="https://openrouter.ai/api/v1",
        api_key_env="OPENROUTER_API_KEY",
        description="test",
    )


async def _stream(chunks: list[Any]) -> AsyncIterator[Any]:
    for chunk in chunks:
        yield chunk


def _make_client() -> MagicMock:
    """Client whose first turn calls write_file and whose second turn is final text."""
    write_args = json.dumps({"path": _TARGET_NAME, "content": _TARGET_CONTENT})
    turn_one = [tool_chunk(0, "call-1", "write_file", write_args)]
    turn_two = [text_chunk(_FINAL_TEXT)]

    client = MagicMock()
    client.close = AsyncMock()
    client.chat.completions.create = AsyncMock(side_effect=[_stream(turn_one), _stream(turn_two)])
    return client


def _make_context(cwd: Path) -> ActionContext:
    resolver = MagicMock()
    resolver.resolve.return_value = ("gpt-4o-mini", "openrouter")
    return ActionContext(  # type: ignore[arg-type]
        pipeline_name="test-pipeline",
        run_id="run-12345678",
        params={
            "prompt": f"Write {_TARGET_NAME}.",
            "profile": "openrouter",
            "allowed_tools": ["write_file"],
        },
        step_name="design",
        step_index=0,
        prior_outputs={},
        resolver=resolver,
        cf_client=MagicMock(),
        cwd=str(cwd),
    )


@pytest.mark.asyncio
async def test_dispatch_tool_call_writes_file_to_disk(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    client = _make_client()

    with (
        patch(f"{_ACTION_MODULE}.get_profile", return_value=_openrouter_profile()),
        patch(f"{_PROVIDER_MODULE}.AsyncOpenAI", return_value=client),
    ):
        result = await DispatchAction().execute(_make_context(tmp_path))

    written = tmp_path / _TARGET_NAME
    assert written.is_file(), "tool call did not produce a file — silent no-op"
    assert written.read_text() == _TARGET_CONTENT

    assert result.success is True
    # The final turn's text, not the tool-call turn.
    assert result.outputs["response"] == _FINAL_TEXT


@pytest.mark.asyncio
async def test_reverting_cwd_threading_fails_loudly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression guard for D2.

    Reverting the threading means ``one_shot_dispatch`` passes ``cwd=None`` again.
    The agent's constructor check then raises rather than running toolless, and the
    dispatch surfaces a failed ActionResult with no file written.
    """
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    # Patches the telemetry-carrying entry point the action actually calls (slice 265);
    # patching the bare one_shot_dispatch would guard nothing.
    original = one_shot_dispatch_with_telemetry

    async def _without_cwd(**kwargs: Any) -> tuple[str, dict[str, object]]:
        kwargs["cwd"] = None
        return await original(**kwargs)

    with (
        patch(f"{_ACTION_MODULE}.get_profile", return_value=_openrouter_profile()),
        patch(f"{_PROVIDER_MODULE}.AsyncOpenAI", return_value=_make_client()),
        patch(f"{_ACTION_MODULE}.one_shot_dispatch_with_telemetry", _without_cwd),
    ):
        result = await DispatchAction().execute(_make_context(tmp_path))

    assert result.success is False
    assert "cwd" in (result.error or "")
    assert not (tmp_path / _TARGET_NAME).exists()


# ---------------------------------------------------------------------------
# Tool-use telemetry on ActionResult.metadata (slice 265, task 22)
# ---------------------------------------------------------------------------


def _tool_less_context(cwd: Path) -> ActionContext:
    """Same context with no allowed_tools — the "never offered" case."""
    resolver = MagicMock()
    resolver.resolve.return_value = ("gpt-4o-mini", "openrouter")
    return ActionContext(  # type: ignore[arg-type]
        pipeline_name="test-pipeline",
        run_id="run-12345678",
        params={"prompt": "Say hello.", "profile": "openrouter"},
        step_name="design",
        step_index=0,
        prior_outputs={},
        resolver=resolver,
        cf_client=MagicMock(),
        cwd=str(cwd),
    )


@pytest.mark.asyncio
async def test_dispatch_result_metadata_carries_tools_given_and_calls_made(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    client = _make_client()

    with (
        patch(f"{_ACTION_MODULE}.get_profile", return_value=_openrouter_profile()),
        patch(f"{_PROVIDER_MODULE}.AsyncOpenAI", return_value=client),
    ):
        result = await DispatchAction().execute(_make_context(tmp_path))

    assert result.success is True
    assert result.metadata["tools_given"] == ["write_file"]
    assert result.metadata["tool_calls_made"] == 1


@pytest.mark.asyncio
async def test_dispatch_result_metadata_omits_tools_keys_when_no_tools_configured(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    client = MagicMock()
    client.close = AsyncMock()
    client.chat.completions.create = AsyncMock(return_value=_stream([text_chunk("hello")]))

    with (
        patch(f"{_ACTION_MODULE}.get_profile", return_value=_openrouter_profile()),
        patch(f"{_PROVIDER_MODULE}.AsyncOpenAI", return_value=client),
    ):
        result = await DispatchAction().execute(_tool_less_context(tmp_path))

    assert result.success is True
    assert "tools_given" not in result.metadata
    assert "tool_calls_made" not in result.metadata


@pytest.mark.asyncio
async def test_one_shot_dispatch_return_type_unchanged_for_existing_callers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression guard: one_shot_dispatch still returns a bare str for its other callers."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    client = _make_client()

    with (
        patch(f"{_ACTION_MODULE}.get_profile", return_value=_openrouter_profile()),
        patch(f"{_PROVIDER_MODULE}.AsyncOpenAI", return_value=client),
    ):
        returned = await one_shot_dispatch(
            prompt=f"Write {_TARGET_NAME}.",
            model_id="gpt-4o-mini",
            profile_name="openrouter",
            allowed_tools=["write_file"],
            cwd=str(tmp_path),
        )

    assert isinstance(returned, str)
    assert returned == _FINAL_TEXT
