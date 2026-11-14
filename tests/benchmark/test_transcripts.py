"""Transcript source protocol, registry and lenient JSONL helpers (slice 424 Task 16)."""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.benchmark import transcripts
from squadron.benchmark.transcripts import (
    ToolCall,
    TranscriptResult,
    iter_jsonl,
    register_transcript_source,
    transcript_source_for,
)
from squadron.providers.base import ProfileName


class StubSource:
    def read(self, home: Path) -> TranscriptResult:
        return TranscriptResult(
            tool_calls=(ToolCall(tool="Bash", input={"command": "ls"}),), files_read=1
        )


class TestRegistry:
    def test_registered_source_is_returned(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(transcripts, "_REGISTRY", {})
        source = StubSource()
        register_transcript_source(ProfileName.LOCAL, source)
        assert transcript_source_for(ProfileName.LOCAL) is source

    @pytest.mark.parametrize(
        "profile",
        [ProfileName.OPENAI, ProfileName.OPENROUTER, ProfileName.GEMINI, ProfileName.LOCAL],
    )
    def test_profile_without_a_source_is_none(self, profile: ProfileName) -> None:
        assert transcript_source_for(profile) is None

    @pytest.mark.parametrize("profile", [ProfileName.SDK, ProfileName.OPENAI_OAUTH])
    def test_builtin_profiles_have_a_source(self, profile: ProfileName) -> None:
        assert transcript_source_for(profile) is not None


class TestIterJsonl:
    def test_blank_lines_are_skipped(self, tmp_path: Path) -> None:
        path = tmp_path / "t.jsonl"
        path.write_text('{"a": 1}\n\n   \n{"b": 2}\n')
        problems: list[str] = []
        assert list(iter_jsonl(path, problems)) == [{"a": 1}, {"b": 2}]
        assert problems == []

    @pytest.mark.parametrize("separator", ["\u2028", "\u2029", "\u0085"])
    def test_a_unicode_line_separator_inside_a_json_string_does_not_split_the_line(
        self, tmp_path: Path, separator: str
    ) -> None:
        # JSON allows these characters unescaped inside a string; only "\n" ends a record.
        path = tmp_path / "t.jsonl"
        path.write_text(f'{{"text": "a{separator}b"}}\n{{"b": 2}}\n', encoding="utf-8")
        problems: list[str] = []
        assert list(iter_jsonl(path, problems)) == [{"text": f"a{separator}b"}, {"b": 2}]
        assert problems == []

    def test_windows_line_endings_are_read(self, tmp_path: Path) -> None:
        path = tmp_path / "t.jsonl"
        path.write_bytes(b'{"a": 1}\r\n{"b": 2}\r\n')
        problems: list[str] = []
        assert list(iter_jsonl(path, problems)) == [{"a": 1}, {"b": 2}]
        assert problems == []

    def test_bad_line_is_recorded_and_reading_continues(self, tmp_path: Path) -> None:
        path = tmp_path / "t.jsonl"
        path.write_text('{"a": 1}\nnot json\n[1, 2]\n{"b": 2}\n')
        problems: list[str] = []
        assert list(iter_jsonl(path, problems)) == [{"a": 1}, {"b": 2}]
        assert len(problems) == 2
        assert "t.jsonl:2" in problems[0]
        assert "not a JSON object" in problems[1]

    def test_unreadable_file_is_a_problem(self, tmp_path: Path) -> None:
        problems: list[str] = []
        assert list(iter_jsonl(tmp_path / "missing.jsonl", problems)) == []
        assert "cannot read" in problems[0]
