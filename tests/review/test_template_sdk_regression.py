"""Migrated templates must reach the SDK reviewer with the vocabulary it had before.

Slice 265 rewrote all seven shipped templates from Claude vocabulary (``Read``, ``Glob``,
``Grep``, ``Bash``) to the canonical squadron names, and added a translation step at the SDK
config-build edge. This is SC3's literal assertion, run against the real shipped templates
rather than a synthetic fixture: the SDK path must be byte-for-byte unchanged in effect, so
the migration cannot silently degrade Claude-backed reviews while fixing non-SDK ones.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadron.core.models import AgentConfig
from squadron.providers.sdk.provider import ClaudeSDKProvider
from squadron.review.templates import get_template, load_all_templates

_AGENT_PATCH = "squadron.providers.sdk.agent.ClaudeSDKAgent"

# The pre-migration Claude-name list each shipped template must still produce.
# code.yaml is the one deliberate difference — see test_code_template_drops_bash.
# Registered names, not filenames — the judge templates load as "judge.<name>".
_UNCHANGED_TEMPLATES = [
    "arch",
    "judge.findings-addressed",
    "judge.slice-vs-arch",
    "judge.tasks-vs-slice",
    "slice",
    "tasks",
]
_EXPECTED_CLAUDE_NAMES = ["Read", "Glob", "Grep"]


async def _built_allowed_tools(template_name: str) -> list[str]:
    """Load a shipped template and return the allowed_tools on its built SDK options."""
    load_all_templates()
    template = get_template(template_name)
    assert template is not None, f"shipped template {template_name!r} not found"

    config = AgentConfig(
        name=f"review-{template_name}",
        agent_type="sdk",
        provider="sdk",
        allowed_tools=template.allowed_tools,
        permission_mode=template.permission_mode,
        setting_sources=template.setting_sources,
    )
    with patch(_AGENT_PATCH, create=True) as mock_cls:
        mock_cls.return_value = MagicMock()
        await ClaudeSDKProvider().create_agent(config)
        options = mock_cls.call_args.kwargs["options"]
    return list(options.allowed_tools)


@pytest.mark.asyncio
@pytest.mark.parametrize("template_name", _UNCHANGED_TEMPLATES)
async def test_migrated_template_builds_identical_claude_tool_list(template_name: str) -> None:
    assert await _built_allowed_tools(template_name) == _EXPECTED_CLAUDE_NAMES


@pytest.mark.asyncio
async def test_code_template_drops_bash() -> None:
    """code.yaml is the single intentional behavior difference (design D6).

    Dropping ``Bash`` changes the ``--allowedTools`` string the CLI is invoked with, not the
    SDK reviewer's actual capability — that is governed by permission mode, which this test
    deliberately says nothing about. Tracked as issue #69.
    """
    built = await _built_allowed_tools("code")

    assert built == _EXPECTED_CLAUDE_NAMES
    assert "Bash" not in built


@pytest.mark.asyncio
async def test_every_shipped_template_uses_canonical_names_only() -> None:
    """No template may still declare Claude vocabulary — the raise would fire at runtime."""
    load_all_templates()
    for name in [*_UNCHANGED_TEMPLATES, "code"]:
        template = get_template(name)
        assert template is not None
        assert template.allowed_tools == ["read_file", "list_files", "grep"], name
