"""Claude Code transcripts (profile ``sdk``), slice 424 D6.

Layout (Task 13 spike, DEVLOG 2026-11-14): ``<home>/.claude/projects/<cwd>/<session>.jsonl``,
plus ``<session>/subagents/agent-<id>.jsonl`` when a subagent ran. A tool call is a
``tool_use`` block of an ``assistant`` entry's ``message.content``; ``Bash`` carries its
shell command as ``input["command"]`` already.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from squadron.benchmark.transcripts import (
    ToolCall,
    TranscriptResult,
    as_list,
    as_mapping,
    iter_jsonl,
    register_transcript_source,
    sorted_files,
)
from squadron.providers.base import ProfileName

TRANSCRIPT_DIRECTORY = Path(".claude") / "projects"
_ASSISTANT_ENTRY = "assistant"
_TOOL_USE_BLOCK = "tool_use"


def _tool_calls_of(entry: Mapping[str, object]) -> list[ToolCall]:
    if entry.get("type") != _ASSISTANT_ENTRY:
        return []
    message = as_mapping(entry.get("message"))
    content = as_list(message.get("content")) if message is not None else None
    calls: list[ToolCall] = []
    for item in content or []:
        block = as_mapping(item)
        if block is None or block.get("type") != _TOOL_USE_BLOCK:
            continue
        name = block.get("name")
        tool_input = as_mapping(block.get("input"))
        if isinstance(name, str) and tool_input is not None:
            calls.append(ToolCall(tool=name, input=tool_input))
    return calls


class ClaudeTranscriptSource:
    def read(self, home: Path) -> TranscriptResult:
        directory = home / TRANSCRIPT_DIRECTORY
        files = sorted_files(directory, "*.jsonl")
        problems: list[str] = []
        if not files:
            problems.append(f"no Claude Code transcript files under {directory}")
        calls: list[ToolCall] = []
        for path in files:
            for entry in iter_jsonl(path, problems):
                calls.extend(_tool_calls_of(entry))
        return TranscriptResult(
            tool_calls=tuple(calls), files_read=len(files), problems=tuple(problems)
        )


register_transcript_source(ProfileName.SDK, ClaudeTranscriptSource())
