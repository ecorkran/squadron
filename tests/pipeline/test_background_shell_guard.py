"""Pipeline dispatches may not start background shells (issue 199)."""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
from claude_agent_sdk import HookContext

from squadron.pipeline.background_shell_guard import (
    DENIAL_REASON,
    deny_background_shell,
    pipeline_hooks,
)

_CONTEXT = cast(HookContext, MagicMock())


def _pre_tool_use(tool_name: str, tool_input: dict[str, Any]) -> Any:
    return {"hook_event_name": "PreToolUse", "tool_name": tool_name, "tool_input": tool_input}


@pytest.mark.asyncio
async def test_background_bash_is_denied_with_a_reason_the_agent_can_act_on() -> None:
    output = await deny_background_shell(
        _pre_tool_use("Bash", {"command": "pytest", "run_in_background": True}), "t1", _CONTEXT
    )

    decision = output["hookSpecificOutput"]
    assert decision["permissionDecision"] == "deny"
    assert decision["permissionDecisionReason"] == DENIAL_REASON
    assert "foreground" in DENIAL_REASON


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool_name", "tool_input"),
    [
        ("Bash", {"command": "pytest"}),
        ("Bash", {"command": "pytest", "run_in_background": False}),
        ("Read", {"file_path": "x", "run_in_background": True}),
    ],
)
async def test_foreground_bash_and_other_tools_are_left_alone(
    tool_name: str, tool_input: dict[str, Any]
) -> None:
    output = await deny_background_shell(_pre_tool_use(tool_name, tool_input), "t1", _CONTEXT)

    assert output == {}


def test_pipeline_hooks_route_bash_pre_tool_use_to_the_guard() -> None:
    (matcher,) = pipeline_hooks()["PreToolUse"]

    assert matcher.matcher == "Bash"
    assert matcher.hooks == [deny_background_shell]


@pytest.mark.asyncio
async def test_open_pipeline_session_installs_the_guard() -> None:
    from squadron.pipeline import sdk_session

    captured: dict[str, Any] = {}

    def fake_client(*, options: Any) -> MagicMock:
        captured["options"] = options
        client = MagicMock()
        client.connect = MagicMock(side_effect=lambda: _done())
        return client

    async def _done() -> None:
        return None

    with (
        patch.object(sdk_session, "ClaudeSDKClient", side_effect=fake_client),
        patch.object(sdk_session, "get_typed_config", return_value=False),
    ):
        await sdk_session.open_pipeline_session()

    assert captured["options"].hooks == pipeline_hooks()
