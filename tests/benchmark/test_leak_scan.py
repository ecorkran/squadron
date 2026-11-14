"""The leak scan verdicts (slice 424 Task 21; the design's walkthrough step 7)."""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

import pytest

from squadron.benchmark.leak_scan import (
    LEAK_RULES_VERSION,
    LeakRules,
    build_leak_rules,
    scan,
)
from squadron.benchmark.transcripts import ToolCall, TranscriptResult, transcript_source_for
from squadron.metrology.benchmark_replay_enums import LeakRule, LeakVerdict
from squadron.metrology.benchmark_replay_models import MAX_LEAK_EXCERPT_CHARS, MAX_LEAK_HITS
from squadron.providers.base import ProfileName
from tests.benchmark.test_leak_rule_paths import Layout

FIXTURES = Path(__file__).parent / "fixtures" / "transcripts"
DISTRIBUTION = "squadron-ai"


class ScriptedSource:
    """A source returning fixed calls, for rule tests that need no files."""

    def __init__(self, *calls: ToolCall, files_read: int = 1, problems: tuple[str, ...] = ()):
        self._result = TranscriptResult(tool_calls=calls, files_read=files_read, problems=problems)

    def read(self, home: Path) -> TranscriptResult:
        return self._result


@pytest.fixture
def layout(tmp_path: Path) -> Layout:
    return Layout(tmp_path)


@pytest.fixture
def rules(layout: Layout) -> LeakRules:
    return build_leak_rules(
        tree=layout.tree,
        home=layout.sandbox_home,
        output_dir=layout.output,
        real_home=layout.real_home,
        repo_root=layout.repo_root,
        install_location=layout.install,
        uv_cache=layout.uv_cache,
        distribution_name=DISTRIBUTION,
        host_owner="owner",
        host_repo="repo",
    )


def _scan_calls(rules: LeakRules, tmp_path: Path, *calls: ToolCall):
    return scan(ScriptedSource(*calls), tmp_path, rules)


class TestLeaked:
    @pytest.mark.parametrize(
        ("rule", "build"),
        [
            (LeakRule.PATH, lambda x: ToolCall("Read", {"file_path": f"{x.repo_root}/src/a.py"})),
            (LeakRule.GIT_OR_HOST, lambda x: ToolCall("Bash", {"command": "gh issue view 3"})),
            (LeakRule.GIT_OR_HOST, lambda x: ToolCall("Bash", {"command": "git -C /elsewhere log"})),
            (LeakRule.OWN_PACKAGE, lambda x: ToolCall("Bash", {"command": f"uvx {DISTRIBUTION}"})),
        ],
        ids=["read-checkout", "gh", "git-C-outside", "uvx-own-package"],
    )
    def test_each_rule_is_leaked_with_the_hit_recorded(
        self, rules: LeakRules, layout: Layout, tmp_path: Path, rule: LeakRule, build: object
    ) -> None:
        call = build(layout)  # type: ignore[operator]
        result = _scan_calls(rules, tmp_path, ToolCall("Bash", {"command": "ls"}), call)
        assert result.verdict == LeakVerdict.LEAKED
        assert [hit.rule for hit in result.hits] == [rule]
        assert result.hits[0].tool == call.tool
        assert result.tool_calls_seen == 2
        assert result.rules_version == LEAK_RULES_VERSION

    def test_one_call_can_hit_two_rules(self, rules: LeakRules, tmp_path: Path) -> None:
        call = ToolCall("Bash", {"command": f"cat ~/x && uvx {DISTRIBUTION}"})
        result = _scan_calls(rules, tmp_path, call)
        assert {hit.rule for hit in result.hits} == {LeakRule.PATH, LeakRule.OWN_PACKAGE}

    def test_twenty_five_hits_record_twenty(self, rules: LeakRules, tmp_path: Path) -> None:
        calls = [ToolCall("Bash", {"command": f"gh issue view {n}"}) for n in range(25)]
        result = _scan_calls(rules, tmp_path, *calls)
        assert result.verdict == LeakVerdict.LEAKED
        assert len(result.hits) == MAX_LEAK_HITS
        assert "25 hits" in result.detail
        assert result.tool_calls_seen == 25

    def test_long_excerpt_is_cut_to_the_limit(self, rules: LeakRules, tmp_path: Path) -> None:
        command = "gh issue view " + "9" * 1000
        result = _scan_calls(rules, tmp_path, ToolCall("Bash", {"command": command}))
        assert len(result.hits[0].excerpt) == MAX_LEAK_EXCERPT_CHARS

    def test_a_hit_wins_over_unreadable_items(self, rules: LeakRules, tmp_path: Path) -> None:
        source = ScriptedSource(
            ToolCall("Bash", {"command": "gh x"}), files_read=0, problems=("unreadable",)
        )
        assert scan(source, tmp_path, rules).verdict == LeakVerdict.LEAKED


class TestFixtureDriven:
    @pytest.mark.parametrize("profile", [ProfileName.SDK, ProfileName.OPENAI_OAUTH])
    def test_clean_fixture_transcript_is_no_leak_detected(
        self, rules: LeakRules, tmp_path: Path, profile: ProfileName
    ) -> None:
        home = tmp_path / "scrubbed-home"
        shutil.copytree(FIXTURES / profile.value, home)
        source = transcript_source_for(profile)
        assert source is not None
        result = scan(source, home, rules)
        assert result.verdict == LeakVerdict.NO_LEAK_DETECTED
        assert result.tool_calls_seen > 0
        assert result.hits == ()
        assert result.rules_version == LEAK_RULES_VERSION


class TestUnavailable:
    def _scan_home(self, rules: LeakRules, home: Path, profile: ProfileName):
        source = transcript_source_for(profile)
        assert source is not None
        return scan(source, home, rules)

    @pytest.mark.parametrize("profile", [ProfileName.SDK, ProfileName.OPENAI_OAUTH])
    def test_no_transcript_files(
        self, rules: LeakRules, tmp_path: Path, caplog: pytest.LogCaptureFixture, profile: ProfileName
    ) -> None:
        with caplog.at_level(logging.WARNING):
            result = self._scan_home(rules, tmp_path, profile)
        assert result.verdict == LeakVerdict.SCAN_UNAVAILABLE
        assert "no " in result.detail
        assert any(r.levelno == logging.WARNING and "unavailable" in r.message for r in caplog.records)

    def test_unparseable_file(
        self, rules: LeakRules, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        home = tmp_path / "home"
        shutil.copytree(FIXTURES / "sdk", home)
        (home / ".claude/projects/broken.jsonl").write_text("{not json\n")
        with caplog.at_level(logging.WARNING):
            result = self._scan_home(rules, home, ProfileName.SDK)
        assert result.verdict == LeakVerdict.SCAN_UNAVAILABLE
        assert "broken.jsonl:1" in result.detail
        assert result.tool_calls_seen > 0
        assert any(r.levelno == logging.WARNING for r in caplog.records)

    def test_unreadable_tool_use_items_leave_zero_calls(
        self, rules: LeakRules, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        home = tmp_path / "home"
        (home / ".claude/projects/p").mkdir(parents=True)
        entry = {
            "type": "assistant",
            "message": {"content": [{"type": "tool_use", "name": "Bash", "input": "not-a-dict"}]},
        }
        (home / ".claude/projects/p/s.jsonl").write_text(json.dumps(entry) + "\n")
        with caplog.at_level(logging.WARNING):
            result = self._scan_home(rules, home, ProfileName.SDK)
        assert result.verdict == LeakVerdict.SCAN_UNAVAILABLE
        assert result.tool_calls_seen == 0
        assert any(r.levelno == logging.WARNING for r in caplog.records)

    def test_unreadable_codex_call_items_leave_zero_calls(
        self, rules: LeakRules, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        home = tmp_path / "home"
        (home / ".codex/sessions/2026/11/14").mkdir(parents=True)
        payload = {"type": "custom_tool_call", "name": "exec", "input": 7}
        entry = {"type": "response_item", "payload": payload}
        (home / ".codex/sessions/2026/11/14/rollout-x.jsonl").write_text(json.dumps(entry) + "\n")
        with caplog.at_level(logging.WARNING):
            result = self._scan_home(rules, home, ProfileName.OPENAI_OAUTH)
        assert result.verdict == LeakVerdict.SCAN_UNAVAILABLE
        assert result.tool_calls_seen == 0

    @pytest.mark.parametrize(
        ("profile", "relative", "entry"),
        [
            (
                ProfileName.SDK,
                ".claude/projects/p/s.jsonl",
                {"type": "user", "message": {"content": "hi"}},
            ),
            (
                ProfileName.OPENAI_OAUTH,
                ".codex/sessions/2026/11/14/rollout-x.jsonl",
                {"type": "response_item", "payload": {"type": "message"}},
            ),
        ],
    )
    def test_a_transcript_with_no_tool_calls_is_never_clean(
        self,
        rules: LeakRules,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
        profile: ProfileName,
        relative: str,
        entry: dict[str, object],
    ) -> None:
        home = tmp_path / "home"
        (home / relative).parent.mkdir(parents=True)
        (home / relative).write_text(json.dumps(entry) + "\n")
        with caplog.at_level(logging.WARNING):
            result = self._scan_home(rules, home, profile)
        assert result.verdict == LeakVerdict.SCAN_UNAVAILABLE
        assert "no tool calls" in result.detail
        assert any(r.levelno == logging.WARNING for r in caplog.records)

    def test_unavailable_result_carries_rules_version_and_no_hits(
        self, rules: LeakRules, tmp_path: Path
    ) -> None:
        result = scan(ScriptedSource(files_read=1), tmp_path, rules)
        assert (result.rules_version, result.hits) == (LEAK_RULES_VERSION, ())

    def test_clean_calls_with_a_problem_are_unavailable_not_clean(
        self, rules: LeakRules, tmp_path: Path
    ) -> None:
        source = ScriptedSource(ToolCall("Bash", {"command": "ls"}), problems=("unreadable item",))
        result = scan(source, tmp_path, rules)
        assert result.verdict == LeakVerdict.SCAN_UNAVAILABLE
        assert "unreadable item" in result.detail
