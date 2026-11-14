"""ClaudeTranscriptSource against the Task 13 ``sdk`` fixtures (slice 424 Task 17)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from squadron.benchmark.transcript_claude import ClaudeTranscriptSource
from squadron.benchmark.transcripts import transcript_source_for
from squadron.providers.base import ProfileName

FIXTURE = Path(__file__).parent / "fixtures" / "transcripts" / "sdk"
TOOLS_SESSION = Path(
    ".claude/projects/-home-user-bench-spike-sdk-tools/61ba211a-8a50-41ce-adf4-a79ff32d58bf.jsonl"
)
SUBAGENT_FILE_GLOB = "agent-*.jsonl"


@pytest.fixture
def home(tmp_path: Path) -> Path:
    fake_home = tmp_path / "home"
    shutil.copytree(FIXTURE, fake_home)
    return fake_home


def _calls(home: Path) -> list[tuple[str, dict[str, object]]]:
    result = ClaudeTranscriptSource().read(home)
    return [(call.tool, dict(call.input)) for call in result.tool_calls]


class TestFixtureDriven:
    def test_fixture_tool_calls_are_extracted(self, home: Path) -> None:
        result = ClaudeTranscriptSource().read(home)
        by_tool = {call.tool: dict(call.input) for call in result.tool_calls}
        assert by_tool["Bash"] == {"command": "ls", "description": "scrubbed"}
        assert by_tool["Agent"].keys() == {"description", "prompt", "subagent_type"}
        reads = [call for call in result.tool_calls if call.tool == "Read"]
        assert {call.input["file_path"] for call in reads} == {
            "/home/user/bench/spike-sdk-tools/hello.txt",
            "/home/user/bench/spike-sdk-subagent/hello.txt",
        }
        assert result.problems == ()
        assert result.files_read == 3

    def test_subagent_file_calls_are_included(self, home: Path) -> None:
        subagent_file = next(home.rglob(SUBAGENT_FILE_GLOB))
        assert "subagents" in subagent_file.parts
        assert ("Read", {"file_path": "/home/user/bench/spike-sdk-subagent/hello.txt"}) in _calls(home)

    def test_registered_for_the_sdk_profile(self) -> None:
        assert isinstance(transcript_source_for(ProfileName.SDK), ClaudeTranscriptSource)


class TestSyntheticLines:
    def test_unknown_entry_type_is_skipped_and_extra_call_found(self, home: Path) -> None:
        before = len(_calls(home))
        extra = [
            {
                "type": "future-entry-type",
                "message": {"content": [{"type": "tool_use", "name": "X", "input": {}}]},
            },
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "text", "text": "scrubbed"},
                        {"type": "tool_use", "name": "Grep", "input": {"pattern": "/etc", "path": "/"}},
                    ]
                },
            },
        ]
        with (home / TOOLS_SESSION).open("a") as handle:
            for entry in extra:
                handle.write(json.dumps(entry) + "\n")
        calls = _calls(home)
        assert len(calls) == before + 1
        assert ("Grep", {"pattern": "/etc", "path": "/"}) in calls

    def test_non_json_file_yields_a_problem(self, home: Path) -> None:
        (home / ".claude/projects/broken.jsonl").write_text("this is not json\n")
        result = ClaudeTranscriptSource().read(home)
        assert any("broken.jsonl:1" in problem for problem in result.problems)
        assert len(result.tool_calls) == len(_calls(home))

    def test_empty_home_yields_a_problem(self, tmp_path: Path) -> None:
        result = ClaudeTranscriptSource().read(tmp_path)
        assert result.tool_calls == ()
        assert result.files_read == 0
        assert "no Claude Code transcript files" in result.problems[0]

    def test_directory_without_files_yields_a_problem(self, tmp_path: Path) -> None:
        (tmp_path / ".claude/projects").mkdir(parents=True)
        result = ClaudeTranscriptSource().read(tmp_path)
        assert "no Claude Code transcript files" in result.problems[0]
