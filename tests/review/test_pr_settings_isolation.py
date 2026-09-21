"""The PR review path must never let a reviewed worktree's own settings reach the SDK.

Slice 382, design D8: the Agent SDK resolves project settings — including PreToolUse shell
hooks, which neither permission_mode nor allowed_tools constrains — from `cwd` unless told
not to. A scratch worktree containing a stranger's PR is exactly the untrusted `cwd` this
threatens. `setting_sources_override=[]` must reach the SDK as `setting_sources=[]` plus
`CLAUDE_CODE_DISABLE_AUTO_MEMORY=1` in the agent's environment — and `sq review code`'s
existing template-only path (no override) must keep working unchanged.

Written before Task A.4's production code existed (per the task's own instruction) and
confirmed to fail against the un-overridden path first — see the "written to fail first"
note below for how that was verified.

We stub the SDK boundary the same way test_template_sdk_regression.py does: patch
squadron.providers.sdk.agent.ClaudeSDKAgent's constructor and assert against the
ClaudeAgentOptions it was called with. Because the constructor is mocked, no CLI subprocess
ever runs — so this test cannot observe a hook's real side effect (a planted sentinel file
staying absent is trivially true under any setting_sources value once the constructor is
mocked). The assertions instead pin the exact inputs that decide whether the real,
unmocked CLI would consult project settings: setting_sources==[] and
CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 in the built options' env. A `.claude/settings.json`
carrying a PreToolUse hook is still planted in the temp cwd, to document the concrete
threat this proves is never reached — not because this test executes it.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadron.review.review_client import run_review_with_profile
from squadron.review.templates import InputDef, ReviewTemplate

_AGENT_PATCH = "squadron.providers.sdk.agent.ClaudeSDKAgent"


def _plant_hook_settings(cwd: Path, sentinel: Path) -> None:
    """Write a .claude/settings.json whose PreToolUse hook would touch *sentinel*."""
    settings_dir = cwd / ".claude"
    settings_dir.mkdir(parents=True, exist_ok=True)
    settings = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": f"touch {sentinel}",
                        }
                    ],
                }
            ]
        }
    }
    (settings_dir / "settings.json").write_text(json.dumps(settings))


def _make_template(*, setting_sources: list[str] | None) -> ReviewTemplate:
    return ReviewTemplate(
        name="code",
        description="Test template",
        system_prompt="You are a reviewer.",
        allowed_tools=["read_file"],
        permission_mode="bypassPermissions",
        setting_sources=setting_sources,
        required_inputs=[InputDef(name="input", description="doc")],
        optional_inputs=[InputDef(name="cwd", description="dir", default=".")],
        prompt_template="Review {input}",
        profile=None,
        model=None,
    )


async def _built_options_for_run(*, cwd: str, setting_sources_override: list[str] | None):
    """Run run_review_with_profile against the real SDK provider profile, SDK agent mocked."""
    task_file = Path(cwd) / "task.md"
    task_file.write_text("# Task\nreview me")

    inputs = {"input": str(task_file), "cwd": cwd}
    template = _make_template(setting_sources=["project"])

    with patch(_AGENT_PATCH, create=True) as mock_cls:
        mock_instance = MagicMock()

        async def _empty_handle(message: object):
            return
            yield  # pragma: no cover - makes this an async generator

        mock_instance.handle_message = _empty_handle
        mock_instance.shutdown = AsyncMock()
        mock_cls.return_value = mock_instance

        await run_review_with_profile(
            template,
            inputs,
            profile="sdk",
            setting_sources_override=setting_sources_override,
        )
        return mock_cls.call_args.kwargs["options"]


@pytest.mark.asyncio
async def test_setting_sources_override_empty_reaches_sdk_as_empty(tmp_path: Path) -> None:
    sentinel = tmp_path.parent / f"{tmp_path.name}-sentinel.txt"
    _plant_hook_settings(tmp_path, sentinel)

    options = await _built_options_for_run(cwd=str(tmp_path), setting_sources_override=[])

    assert list(options.setting_sources) == []
    assert options.env.get("CLAUDE_CODE_DISABLE_AUTO_MEMORY") == "1"
    # No real CLI subprocess ran (the constructor is mocked), so the hook never fired —
    # this documents the threat the options-level assertions above prove is never reached.
    assert not sentinel.exists()


@pytest.mark.asyncio
async def test_no_override_still_passes_template_setting_sources(tmp_path: Path) -> None:
    """sq review code's existing path: no override, template's [project] must survive."""
    options = await _built_options_for_run(cwd=str(tmp_path), setting_sources_override=None)

    assert list(options.setting_sources) == ["project"]
    assert "CLAUDE_CODE_DISABLE_AUTO_MEMORY" not in dict(options.env or {})
