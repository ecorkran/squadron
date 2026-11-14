"""Codex transcripts (profile ``openai-oauth``), slice 424 D6.

Layout (Task 13 spike, DEVLOG 2026-11-14): ``<home>/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl``,
entries ``{timestamp, ordinal, type, payload}``. A tool call is ``type: response_item`` with
``payload.type: custom_tool_call``, ``payload.name: exec`` and ``payload.input`` a JavaScript
snippet: the shell command is the ``cmd`` string literal of its ``tools.exec_command({...})``
call, so it is read out of that source text and exposed as ``input["command"]``.

Only ``custom_tool_call`` was observed. Any other ``*_call`` payload type is not guessed at:
it is recorded in ``problems`` so the loss is visible.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path

from squadron.benchmark.transcripts import (
    ToolCall,
    TranscriptResult,
    as_mapping,
    iter_jsonl,
    register_transcript_source,
    sorted_files,
)
from squadron.providers.base import ProfileName

TRANSCRIPT_DIRECTORY = Path(".codex") / "sessions"
ROLLOUT_PATTERN = "rollout-*.jsonl"
SHELL_TOOL_NAME = "exec_command"
_RESPONSE_ITEM = "response_item"
_CUSTOM_TOOL_CALL = "custom_tool_call"
_CALL_SUFFIX = "_call"
_STRING_LITERAL = r"\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*'|`(?:[^`\\]|\\.)*`"
_COMMAND_LITERAL = re.compile(
    rf"tools\s*\.\s*{SHELL_TOOL_NAME}\s*\(\s*\{{[^}}]*?\bcmd\s*:\s*({_STRING_LITERAL})", re.DOTALL
)
_TOOLS_USED = re.compile(r"\btools\s*\.\s*(\w+)")


def _decode_js_string(literal: str) -> str | None:
    """The value of a JS string literal; ``None`` when it uses an escape JSON cannot read."""
    body = literal[1:-1]
    if literal[0] != '"':
        body = body.replace("\\" + literal[0], literal[0]).replace('"', '\\"')
    try:
        decoded: object = json.loads(f'"{body}"')
    except json.JSONDecodeError:
        return None
    return decoded if isinstance(decoded, str) else None


def _calls_from_source(name: str, source: str, where: str, problems: list[str]) -> list[ToolCall]:
    commands = [_decode_js_string(literal) for literal in _COMMAND_LITERAL.findall(source)]
    readable = [command for command in commands if command is not None]
    other_tools = {tool for tool in _TOOLS_USED.findall(source) if tool != SHELL_TOOL_NAME}
    calls = [ToolCall(tool=SHELL_TOOL_NAME, input={"command": command}) for command in readable]
    if readable and not other_tools and len(readable) == len(commands):
        return calls
    # The snippet does more than literal shell commands: scan its raw text as one command.
    problems.append(f"{where}: exec source not fully readable as shell commands; scanned as text")
    return [*calls, ToolCall(tool=name, input={"command": source})]


def _calls_of(entry: Mapping[str, object], where: str, problems: list[str]) -> list[ToolCall]:
    if entry.get("type") != _RESPONSE_ITEM:
        return []
    payload = as_mapping(entry.get("payload"))
    if payload is None:
        return []
    kind = payload.get("type")
    if kind == _CUSTOM_TOOL_CALL:
        name, source = payload.get("name"), payload.get("input")
        if isinstance(name, str) and isinstance(source, str):
            return _calls_from_source(name, source, where, problems)
        problems.append(f"{where}: custom_tool_call without a name and string input")
    elif isinstance(kind, str) and kind.endswith(_CALL_SUFFIX):
        problems.append(f"{where}: unrecognized call item type '{kind}'")
    return []


class CodexTranscriptSource:
    def read(self, home: Path) -> TranscriptResult:
        directory = home / TRANSCRIPT_DIRECTORY
        files = sorted_files(directory, ROLLOUT_PATTERN)
        problems: list[str] = []
        if not files:
            problems.append(f"no Codex rollout files under {directory}")
        calls: list[ToolCall] = []
        for path in files:
            for entry in iter_jsonl(path, problems):
                calls.extend(_calls_of(entry, path.name, problems))
        return TranscriptResult(
            tool_calls=tuple(calls), files_read=len(files), problems=tuple(problems)
        )


register_transcript_source(ProfileName.OPENAI_OAUTH, CodexTranscriptSource())
