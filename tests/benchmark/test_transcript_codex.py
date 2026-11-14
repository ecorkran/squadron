"""CodexTranscriptSource against the Task 13 ``openai-oauth`` fixture (slice 424 Task 18)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from squadron.benchmark.transcript_codex import SHELL_TOOL_NAME, CodexTranscriptSource
from squadron.benchmark.transcripts import transcript_source_for
from squadron.providers.base import ProfileName

FIXTURE = Path(__file__).parent / "fixtures" / "transcripts" / "openai-oauth"


@pytest.fixture
def home(tmp_path: Path) -> Path:
    fake_home = tmp_path / "home"
    shutil.copytree(FIXTURE, fake_home)
    return fake_home


def _rollout(home: Path) -> Path:
    return next(home.rglob("rollout-*.jsonl"))


def _append(home: Path, *entries: dict[str, object]) -> None:
    with _rollout(home).open("a") as handle:
        for entry in entries:
            handle.write(json.dumps(entry) + "\n")


def _item(payload: dict[str, object]) -> dict[str, object]:
    return {"timestamp": "t", "ordinal": 99, "type": "response_item", "payload": payload}


def _commands(home: Path) -> list[str]:
    result = CodexTranscriptSource().read(home)
    return [str(call.input["command"]) for call in result.tool_calls]


class TestFixtureDriven:
    def test_fixture_commands_are_extracted_from_the_exec_source(self, home: Path) -> None:
        result = CodexTranscriptSource().read(home)
        assert [(call.tool, dict(call.input)) for call in result.tool_calls] == [
            (SHELL_TOOL_NAME, {"command": "cat hello.txt"}),
            (SHELL_TOOL_NAME, {"command": "ls"}),
        ]
        assert result.problems == ()
        assert result.files_read == 1

    def test_registered_for_the_openai_oauth_profile(self) -> None:
        assert isinstance(transcript_source_for(ProfileName.OPENAI_OAUTH), CodexTranscriptSource)


class TestSyntheticItems:
    def test_unknown_item_type_is_skipped(self, home: Path) -> None:
        _append(home, _item({"type": "reasoning", "summary": []}))
        assert _commands(home) == ["cat hello.txt", "ls"]

    def test_two_commands_in_one_snippet_are_both_extracted(self, home: Path) -> None:
        source = (
            'const a = await tools.exec_command({cmd:"git status", max_output_tokens:10});\n'
            "const b = await tools.exec_command({max_output_tokens:5, cmd:'cat \"x y\"'});\n"
        )
        _append(home, _item({"type": "custom_tool_call", "name": "exec", "input": source}))
        assert _commands(home)[2:] == ["git status", 'cat "x y"']

    def test_escapes_in_a_command_are_decoded(self, home: Path) -> None:
        source = 'await tools.exec_command({cmd:"echo \\"hi\\" && ls /tmp"});'
        _append(home, _item({"type": "custom_tool_call", "name": "exec", "input": source}))
        assert _commands(home)[2:] == ['echo "hi" && ls /tmp']

    def test_snippet_with_another_tool_is_scanned_as_text_and_reported(self, home: Path) -> None:
        source = 'const r = await tools.read_file({path:"/etc/hosts"}); text(r);'
        _append(home, _item({"type": "custom_tool_call", "name": "exec", "input": source}))
        result = CodexTranscriptSource().read(home)
        assert str(result.tool_calls[-1].input["command"]) == source
        assert any("scanned as text" in problem for problem in result.problems)

    def test_snippet_with_a_computed_command_is_scanned_as_text_and_reported(self, home: Path) -> None:
        source = "const c = 'ls ' + dir; await tools.exec_command({cmd: c});"
        _append(home, _item({"type": "custom_tool_call", "name": "exec", "input": source}))
        result = CodexTranscriptSource().read(home)
        assert str(result.tool_calls[-1].input["command"]) == source
        assert any("scanned as text" in problem for problem in result.problems)

    def test_unrecognized_call_item_type_is_a_problem(self, home: Path) -> None:
        _append(home, _item({"type": "function_call", "name": "shell", "arguments": "{}"}))
        result = CodexTranscriptSource().read(home)
        assert len(result.tool_calls) == 2
        assert any("unrecognized call item type 'function_call'" in p for p in result.problems)

    def test_call_output_items_are_not_calls(self, home: Path) -> None:
        _append(home, _item({"type": "custom_tool_call_output", "call_id": "c", "output": []}))
        result = CodexTranscriptSource().read(home)
        assert result.problems == ()


class TestMissingAndBadInput:
    def test_missing_directory_yields_a_problem(self, tmp_path: Path) -> None:
        result = CodexTranscriptSource().read(tmp_path)
        assert result.tool_calls == ()
        assert result.files_read == 0
        assert "no Codex rollout files" in result.problems[0]

    def test_bad_jsonl_yields_a_problem_and_good_lines_still_read(self, home: Path) -> None:
        with _rollout(home).open("a") as handle:
            handle.write("{broken\n")
        result = CodexTranscriptSource().read(home)
        assert len(result.tool_calls) == 2
        assert any("not JSON" in problem for problem in result.problems)
