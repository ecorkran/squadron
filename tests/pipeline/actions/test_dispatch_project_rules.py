"""Slice 935: project rules injected into one-shot dispatches and recorded."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from squadron.core.models import AgentConfig
from squadron.pipeline.actions import dispatch_rules
from squadron.pipeline.actions.dispatch import DispatchAction
from squadron.pipeline.models import ActionResult
from squadron.pipeline.steps import StepTypeName
from squadron.pipeline.steps.phase import RULES_STEP_PARAM
from squadron.providers.profiles import ProviderProfile
from squadron.review.rules import RulesSource
from tests.pipeline.actions.dispatch_helpers import (
    DISPATCH_MODULE,
    make_agent_mock,
    make_context,
    make_registry,
    openrouter_profile,
    sdk_profile,
)

_AGENTS_TEXT = "Agents conventions text."
_RULE_TEXT = "General rule text."


def _codex_profile() -> ProviderProfile:
    return ProviderProfile(name="codex", provider="openai-oauth", api_key_env=None, description="test")


def _project(root: Path, *, agents: bool = True) -> None:
    if agents:
        (root / "AGENTS.md").write_text(_AGENTS_TEXT)
    (root / "rules").mkdir()
    (root / "rules" / "general.md").write_text(_RULE_TEXT)


async def _run(
    root: Path, profile: ProviderProfile, step: StepTypeName = StepTypeName.DESIGN
) -> tuple[ActionResult, AgentConfig]:
    ctx = make_context(cwd=str(root), params={"prompt": "Go", RULES_STEP_PARAM: step})
    registry = make_registry(make_agent_mock("done"))
    with (
        patch(f"{DISPATCH_MODULE}.get_registry", return_value=registry),
        patch(f"{DISPATCH_MODULE}.get_profile", return_value=profile),
        patch(f"{DISPATCH_MODULE}.ensure_provider_loaded"),
    ):
        result = await DispatchAction().execute(ctx)
    spawn: AsyncMock = registry.spawn
    config = spawn.call_args.args[0] if spawn.call_args else None
    return result, config  # type: ignore[return-value]


@pytest.mark.asyncio
async def test_non_sdk_dispatch_gets_rules_and_record(tmp_path: Path) -> None:
    _project(tmp_path)
    result, config = await _run(tmp_path, openrouter_profile())

    assert result.success is True
    assert config.instructions is not None
    assert config.instructions.startswith("## Project Rules")
    assert _AGENTS_TEXT in config.instructions
    assert _RULE_TEXT in config.instructions
    record = result.metadata["project_rules"]
    assert record == {
        "conventions": "AGENTS.md",
        "native": False,
        "skipped": [],
        "rules": ["general.md"],
        "dropped": [],
        "chars": len(_AGENTS_TEXT) + len(_RULE_TEXT),
    }


@pytest.mark.asyncio
async def test_sdk_one_shot_instructions_unchanged(tmp_path: Path) -> None:
    _project(tmp_path)
    result, config = await _run(tmp_path, sdk_profile())

    assert config.instructions is None
    assert result.metadata["project_rules"] == {"conventions": "sdk-native"}


@pytest.mark.asyncio
async def test_codex_skips_native_agents_md_but_keeps_rules(tmp_path: Path) -> None:
    _project(tmp_path)
    result, config = await _run(tmp_path, _codex_profile())

    assert config.instructions is not None
    assert _AGENTS_TEXT not in config.instructions
    assert _RULE_TEXT in config.instructions
    record = result.metadata["project_rules"]
    assert isinstance(record, dict)
    assert record["conventions"] == "AGENTS.md"
    assert record["native"] is True


@pytest.mark.asyncio
async def test_no_conventions_and_no_rules_warns(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(dispatch_rules, "resolve_rules_dir", lambda *_: (None, RulesSource.NONE))
    with caplog.at_level(logging.WARNING):
        result, config = await _run(tmp_path, openrouter_profile())

    assert result.success is True
    assert config.instructions is None
    assert "no project rules" in caplog.text
    assert str(tmp_path) in caplog.text
    assert "design" in caplog.text


@pytest.mark.asyncio
async def test_conventions_over_budget_fails_the_action(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _project(tmp_path)
    monkeypatch.setattr(dispatch_rules, "get_config", lambda key, cwd=".": 5)
    with caplog.at_level(logging.WARNING):
        result, _ = await _run(tmp_path, openrouter_profile())

    # A named failure: one ERROR line, no traceback (review F001).
    errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert len(errors) == 1
    assert errors[0].exc_info is None
    assert "project_rules.max_chars" in errors[0].getMessage()

    assert result.success is False
    assert result.error is not None
    assert "project_rules.max_chars" in result.error
    assert "AGENTS.md" in result.error
