"""Tool-use guidance appended to a tool-capable agent's system prompt.

One block, composed once at the agent constructor (design D1) so no caller that passes
tools can skip it. The prose never names a specific tool: the same block serves a review
(``read_file``, ``list_files``, ``grep``) and a design dispatch (``read_file``,
``write_file``). The effective names are rendered in so the model sees what it has.
"""

from __future__ import annotations

__all__ = ["TOOL_USE_HEADING", "compose_system_prompt"]

TOOL_USE_HEADING = "## Tool Use"

# Substance per the slice design's "The guidance block": a hunk cannot prove absence;
# verify before asserting absence or say it is unverified; read only what a claim depends
# on (#81); produce files rather than describe them. Tool-call count is not a goal (#82).
# Batch independent reads (slice 931 D7, #157), worded without naming any tool.
_GUIDANCE_BODY = """\
You have these tools available: {tool_names}.

The prompt may contain a diff or excerpts. A diff shows changed lines and a few lines of
surrounding context; it cannot show a definition, an earlier assignment, a type narrowing,
or a justifying comment that sits outside the hunk. A hunk cannot prove absence.

Before asserting that something is missing, undefined, unhandled, unnarrowed, or
unjustified, open the relevant file with the tools and confirm it. If you cannot confirm
it, say so explicitly — mark the point unverified rather than asserting it.

Use a tool when a claim depends on code that is not in front of you. Do not read files a
claim does not depend on; reading everything is as wrong as reading nothing. The number of
tool calls is not a measure of quality.

When you already know several files you need, request them together — in one call if the
tool accepts several paths, and as parallel tool calls in one turn otherwise. Every turn
resends the whole conversation, so one file per turn is the slowest way to read.

If the task asks for a file to be created or changed, do it with the tools. A description
of a file is not the file."""


def compose_system_prompt(instructions: str | None, tools: list[str] | None) -> str | None:
    """Return ``instructions`` with the tool-use block appended when tools are present.

    With no tools the instructions are returned unchanged, including ``None``, so a
    tool-less agent's prompt is byte-for-byte what its caller supplied. With tools and no
    instructions the block stands alone as the whole system prompt (#40).
    """
    if not tools:
        return instructions

    block = f"{TOOL_USE_HEADING}\n\n{_GUIDANCE_BODY.format(tool_names=', '.join(tools))}"
    if not instructions:
        return block
    return f"{instructions}\n\n{block}"
