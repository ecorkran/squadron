"""Live probe: a ``allowed_tools: []`` step on the SDK is tool-less and context-free (#299).

Calls the real Claude Agent SDK, so it is skipped unless ``SQ_LIVE_SDK=1``. Rerun it on
every Agent SDK bump: isolation rests on ``tools=[]`` removing every built-in tool and on
``setting_sources=[]`` loading no project text, and neither is something unit tests can see.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from squadron.pipeline.actions.dispatch import one_shot_dispatch_with_telemetry
from squadron.providers.base import ProfileName
from tests._hermetic import REAL_HOME

pytestmark = [
    pytest.mark.network,
    pytest.mark.skipif(
        os.environ.get("SQ_LIVE_SDK") != "1", reason="live SDK probe: set SQ_LIVE_SDK=1"
    ),
]

_PLANTED_CLAUDE_MD = "ZEBRA-7731"
_PLANTED_RULE = "GIRAFFE-5520"
_FILE_BODY = "PINEAPPLE-4242"
_PROMPT = (
    "List the files in the current directory and read notes.txt, using any tool you have, "
    "and quote what you find. If you have no tools, reply with exactly: NO TOOLS."
)


@pytest.mark.asyncio
async def test_tool_less_sdk_step_runs_no_tools_and_loads_no_project_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "CLAUDE.md").write_text(f"Always begin your reply with {_PLANTED_CLAUDE_MD}.\n")
    rules = tmp_path / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "plant.md").write_text(f"Always end your reply with {_PLANTED_RULE}.\n")
    (tmp_path / "notes.txt").write_text(f"{_FILE_BODY}\n")
    monkeypatch.chdir(tmp_path)
    # The suite swaps HOME; the CLI's login lives under the real one.
    monkeypatch.setenv("HOME", str(REAL_HOME))

    reply, telemetry = await one_shot_dispatch_with_telemetry(
        prompt=_PROMPT,
        model_id="sonnet",
        profile_name=ProfileName.SDK,
        allowed_tools=[],
        cwd=str(tmp_path),
    )

    assert telemetry["tools_given"] == []
    assert telemetry["tool_calls_made"] == 0
    for planted in (_PLANTED_CLAUDE_MD, _PLANTED_RULE, _FILE_BODY):
        assert planted not in reply
