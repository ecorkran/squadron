"""Leak verdicts for recall stage calls (slice 430 D6, D8)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from squadron.benchmark.leak_rules import LeakRules
from squadron.benchmark.recall.leak_check import (
    LeakCheckError,
    LeakInputs,
    TranscriptLeakChecker,
    leak_judgeable,
)
from squadron.benchmark.recall.stage_runner import StageContext, run_stage
from squadron.benchmark.transcripts import ToolCall, TranscriptResult, TranscriptSource
from squadron.metrology.benchmark_replay_models import LeakScanResult
from squadron.metrology.recall_run_models import RecallLeakVerdict, RecallRun
from squadron.providers.base import ProfileName
from squadron.recipes.recipe import Recipe
from tests.benchmark.recall.scoring_support import make_case
from tests.benchmark.recall.stage_support import (
    output_arg,
    pending_for,
    review_document,
    stage_deps,
    write_json,
    writing_runner,
)

CASE = make_case()  # repo ~/source/repos/demo, host owner/demo, distribution demo


def _repo() -> Path:
    """Expanded at test time: the test harness gives each test its own HOME."""
    return Path(CASE.repo).expanduser()


class FakeSource:
    def __init__(self, result: TranscriptResult) -> None:
        self._result = result

    def read(self, home: Path) -> TranscriptResult:
        return self._result


def _context(tmp_path: Path, profile: ProfileName = ProfileName.SDK) -> StageContext:
    stage = pending_for(CASE, Recipe(name="r", reviewers=("rev",)))[0]
    return StageContext(stage, profile, tmp_path / "tree", tmp_path / "home", tmp_path / "out")


def _inputs(tmp_path: Path) -> LeakInputs:
    return LeakInputs(
        real_home=tmp_path / "real-home",
        install_location=tmp_path / "site/squadron",
        uv_cache=tmp_path / "uv",
    )


def _checker(tmp_path: Path, result: TranscriptResult) -> TranscriptLeakChecker:
    return TranscriptLeakChecker(_inputs(tmp_path), source_for=lambda profile: FakeSource(result))


def test_reading_the_case_repo_by_absolute_path_is_leaked(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    calls = (ToolCall("Bash", {"command": f"cat {_repo()}/src/a.py"}),)
    with caplog.at_level(logging.WARNING):
        verdict = _checker(tmp_path, TranscriptResult(tool_calls=calls, files_read=1)).check(
            _context(tmp_path)
        )
    assert verdict is RecallLeakVerdict.LEAKED
    assert any(
        "case demo-1 run 1 stage review rev" in r.getMessage() and "leaked" in r.getMessage()
        for r in caplog.records
    )


def test_no_transcript_is_scan_unavailable(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        verdict = _checker(tmp_path, TranscriptResult(tool_calls=(), files_read=0)).check(
            _context(tmp_path)
        )
    assert verdict is RecallLeakVerdict.SCAN_UNAVAILABLE
    assert any(
        "stage review rev" in r.getMessage() and "scan_unavailable" in r.getMessage()
        for r in caplog.records
    )


def test_reads_inside_the_sandbox_are_clean(tmp_path: Path) -> None:
    calls = (ToolCall("Read", {"file_path": str(tmp_path / "tree" / "src" / "a.py")}),)
    verdict = _checker(tmp_path, TranscriptResult(tool_calls=calls, files_read=1)).check(
        _context(tmp_path)
    )
    assert verdict is RecallLeakVerdict.NO_LEAK_DETECTED


def test_scan_inputs_include_case_repo_and_host_repo(tmp_path: Path) -> None:
    seen: list[LeakRules] = []

    def capture(source: TranscriptSource, home: Path, rules: LeakRules) -> LeakScanResult:
        seen.append(rules)
        raise AssertionError("stop after capture")

    checker = TranscriptLeakChecker(
        _inputs(tmp_path), source_for=lambda p: FakeSource(TranscriptResult((), 0)), scan=capture
    )
    with pytest.raises(AssertionError):
        checker.check(_context(tmp_path))
    text = repr(seen[0])
    assert str(_repo()) in text and "owner" in text and "demo" in text
    assert str(tmp_path / "tree") in text and str(tmp_path / "real-home") in text


def test_jailed_builtins_are_confined_without_a_scan(tmp_path: Path) -> None:
    def never(source: TranscriptSource, home: Path, rules: LeakRules) -> LeakScanResult:
        raise AssertionError("confined path must not scan")

    checker = TranscriptLeakChecker(_inputs(tmp_path), source_for=lambda p: None, scan=never)
    assert checker.check(_context(tmp_path, ProfileName.OPENROUTER)) is RecallLeakVerdict.CONFINED
    assert leak_judgeable(ProfileName.OPENROUTER, source_for=lambda p: None)


def test_neither_source_nor_jail_raises(tmp_path: Path) -> None:
    checker = TranscriptLeakChecker(_inputs(tmp_path), source_for=lambda p: None)
    with pytest.raises(LeakCheckError):
        checker.check(_context(tmp_path, ProfileName.SDK))
    assert not leak_judgeable(ProfileName.SDK, source_for=lambda p: None)


def test_checker_is_wired_into_the_stage_runner(tmp_path: Path) -> None:
    calls = (ToolCall("Bash", {"command": f"cat {_repo()}/src/a.py"}),)
    checker = TranscriptLeakChecker(
        _inputs(tmp_path), source_for=lambda p: FakeSource(TranscriptResult(calls, 1))
    )
    runner = writing_runner(lambda call: write_json(output_arg(call.argv), review_document([])))
    deps = stage_deps(tmp_path, runner, leak=checker)  # type: ignore[arg-type]
    stage = pending_for(CASE, Recipe(name="r", reviewers=("rev",)))[0]
    (tmp_path / "sandbox").mkdir()
    entry = run_stage(stage, RecallRun(case_id=CASE.case_id, run_index=1), tmp_path / "sandbox", deps)
    assert entry.leak is RecallLeakVerdict.LEAKED
