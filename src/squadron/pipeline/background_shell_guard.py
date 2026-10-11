"""Deny background shells in pipeline dispatches (issue 199).

A shell started with ``run_in_background`` finishes after the dispatch has
returned, and the SDK then hands its completion to the session as a new turn.
The agent resumes work with nobody reading it: the code review judges a stale
commit and two writers share one checkout. Slice 932 D5 left shells out of the
dispatch wait on purpose (they can run forever), so the dispatch cannot wait for
them. Denying them keeps every command in the foreground, where the dispatch's
stall bound applies.
"""

from __future__ import annotations

from typing import Any

from claude_agent_sdk import HookContext, HookMatcher

BASH_TOOL = "Bash"
BACKGROUND_INPUT_KEY = "run_in_background"

DENIAL_REASON = (
    "Background shells are not allowed in a pipeline step: the step ends when your turn "
    "ends, and nothing reads the shell's result afterwards. Run the command in the "
    "foreground and wait for it."
)


async def deny_background_shell(hook_input: Any, tool_use_id: str | None, context: HookContext) -> Any:
    """PreToolUse hook: deny a Bash call that asks to run in the background."""
    if hook_input["tool_name"] != BASH_TOOL:
        return {}
    if not hook_input["tool_input"].get(BACKGROUND_INPUT_KEY):
        return {}
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": DENIAL_REASON,
        }
    }


def pipeline_hooks() -> dict[str, list[HookMatcher]]:
    """The hooks every pipeline SDK session installs."""
    return {"PreToolUse": [HookMatcher(matcher=BASH_TOOL, hooks=[deny_background_shell])]}
