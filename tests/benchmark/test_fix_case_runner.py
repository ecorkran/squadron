"""FixCaseRunner, the producer invoker, instruction files and candidate rebuilding (Task 25)."""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from squadron.benchmark import case_runners
from squadron.benchmark.bench_plan import BenchConfig, Caps
from squadron.benchmark.case_runners import (
    PRODUCER_BRANCH,
    FixCaseRunner,
    case_runner_for,
    register_case_runner,
)
from squadron.benchmark.fix_case_candidate import (
    candidate_from_case,
    issue_number,
    parse_issue_ref,
)
from squadron.benchmark.fix_discovery import FixCandidate
from squadron.benchmark.instruction_files import (
    OUTSIDE_TREE_MARKER,
    UNREADABLE_MARKER,
    instruction_files,
)
from squadron.benchmark.qualify_types import QualifyResult
from squadron.core.process_runner import ProcessResult, SubprocessRunner
from squadron.metrology.benchmark_models import (
    BenchmarkCase,
    CaseKind,
    CaseProvenance,
)
from squadron.metrology.benchmark_replay_enums import ProducerOutcome
from squadron.pipeline.state import RunState
from squadron.providers.base import ProfileName
from squadron.replay.runner import run_sq_subprocess
from tests.benchmark.test_replay_outcome import dispatch, fix_context, fix_run
from tests.metrology.test_benchmark_models import NOW, environment, qualification
from tests.metrology.test_benchmark_store import make_case
from tests.stats.producer_support import action

SQ_PATH = "/abs/path/to/sq"
CAPS = Caps(run_cap_usd=40.0, per_replay_cap_usd=1.5, per_replay_source="--max-cost-per-replay")
CONFIG = BenchConfig("opus", "claude-opus-5-5", "sdk", "high")
RECORD_ID = "implreplay-0123456789ab-0123456789ab-01234567-s0"
PRODUCER_ENV = {"HOME": "/sandbox/home", "ANTHROPIC_API_KEY": "granted"}


def fix_case(source_ref: str = "#7", task: str = "Fix the parser.\nSteps: ünïcode ✓") -> BenchmarkCase:
    case = make_case(task=task)
    provenance = CaseProvenance(source_ref=source_ref, created_at=NOW, built_by="test")
    return case.model_copy(update={"provenance": provenance})


class FakeSandbox:
    """The three things a runner uses of a sandbox."""

    def __init__(self, tmp_path: Path) -> None:
        self.tree = tmp_path / "tree"
        self.output_dir = tmp_path / "tree.out"
        self.tree.mkdir()
        self.output_dir.mkdir()
        self.home = tmp_path / "home"
        self.identity = environment()
        self.profiles: list[ProfileName] = []
        self.branches: list[str] = []

    def keep(self) -> None:
        raise AssertionError("a runner never keeps the sandbox")

    def checkout_branch(self, name: str) -> None:
        self.branches.append(name)

    def producer_env(self, profile: ProfileName) -> dict[str, str]:
        self.profiles.append(profile)
        return dict(PRODUCER_ENV)


class RecordingInvoker:
    def __init__(self, sandbox: FakeSandbox | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self._sandbox = sandbox

    def __call__(self, argv: Any, cwd: Path, env: Any = None) -> ProcessResult:
        # What the sandbox had done by the time sq started.
        self.branches_at_start = list(self._sandbox.branches) if self._sandbox else []
        self.calls.append({"argv": list(argv), "cwd": cwd, "env": env})
        return ProcessResult(tuple(argv), 0, "", "")


def _no_candidate(case: BenchmarkCase) -> FixCandidate:
    pytest.fail("no candidate expected")


def _runner(invoker: RecordingInvoker, **overrides: Any) -> FixCaseRunner:
    arguments: dict[str, Any] = {
        "sq_path": SQ_PATH,
        "invoker": invoker,
        "qualify_deps": None,
        "candidate_for": _no_candidate,
    }
    arguments.update(overrides)
    return FixCaseRunner(**arguments)


class TestRun:
    def test_argv_is_the_design_command_exactly(self, tmp_path: Path) -> None:
        sandbox, invoker = FakeSandbox(tmp_path), RecordingInvoker()
        _runner(invoker).run(fix_case(), CONFIG, sandbox, CAPS, RECORD_ID)
        assert invoker.calls[0]["argv"] == [
            SQ_PATH, "run", "fix", "7",
            "-m", "opus",
            "--producer-only",
            "--max-cost", "1.5",
            "-p", "issue-file=issue.md",
            "-p", "commit-to=current",
            "--io-dir", str(sandbox.output_dir),
            "--run-id", RECORD_ID,
            "--no-pause-hook",
        ]  # fmt: skip

    def test_resume_answers_with_the_remaining_cap_and_no_hook(self, tmp_path: Path) -> None:
        sandbox, invoker = FakeSandbox(tmp_path), RecordingInvoker()
        _runner(invoker).resume(CONFIG, sandbox, RECORD_ID, "decide it", 0.75)
        assert invoker.calls[0]["argv"] == [
            SQ_PATH, "run", "--resume", RECORD_ID,
            "--instructions", "decide it",
            "--max-cost", "0.75",
            "--no-pause-hook",
        ]  # fmt: skip

    def test_the_tree_is_on_the_producer_branch_before_sq_starts(self, tmp_path: Path) -> None:
        sandbox = FakeSandbox(tmp_path)
        invoker = RecordingInvoker(sandbox)
        _runner(invoker).run(fix_case(), CONFIG, sandbox, CAPS, RECORD_ID)
        assert invoker.branches_at_start == [PRODUCER_BRANCH]

    def test_max_cost_is_always_the_per_replay_cap(self, tmp_path: Path) -> None:
        sandbox, invoker = FakeSandbox(tmp_path), RecordingInvoker()
        caps = Caps(40.0, 2.25, "pipeline.max_cost_usd")
        _runner(invoker).run(fix_case(), CONFIG, sandbox, caps, RECORD_ID)
        argv = invoker.calls[0]["argv"]
        assert argv[argv.index("--max-cost") + 1] == "2.25"

    def test_issue_file_holds_the_case_text_byte_for_byte(self, tmp_path: Path) -> None:
        sandbox, invoker = FakeSandbox(tmp_path), RecordingInvoker()
        case = fix_case(task="line one\r\nline two  \n\nünï ✓")
        _runner(invoker).run(case, CONFIG, sandbox, CAPS, RECORD_ID)
        assert (sandbox.output_dir / "issue.md").read_bytes() == case.task_text.encode("utf-8")

    def test_cwd_and_the_producer_env_are_what_the_invoker_received(self, tmp_path: Path) -> None:
        sandbox, invoker = FakeSandbox(tmp_path), RecordingInvoker()
        _runner(invoker).run(fix_case(), CONFIG, sandbox, CAPS, RECORD_ID)
        assert invoker.calls[0]["cwd"] == sandbox.tree
        assert invoker.calls[0]["env"] == PRODUCER_ENV
        assert [str(profile) for profile in sandbox.profiles] == ["sdk"]

    def test_returns_the_process_result(self, tmp_path: Path) -> None:
        result = _runner(RecordingInvoker()).run(
            fix_case(),
            CONFIG,
            FakeSandbox(tmp_path),
            CAPS,
            RECORD_ID,
        )
        assert result.returncode == 0

    @pytest.mark.parametrize("source_ref", ["", "issue-1", "owner/repo", "#"])
    def test_unreadable_issue_ref_fails_explicitly_before_any_invocation(
        self, tmp_path: Path, source_ref: str
    ) -> None:
        invoker = RecordingInvoker()
        with pytest.raises(ValueError, match="no readable issue ref"):
            _runner(invoker).run(
                fix_case(source_ref),
                CONFIG,
                FakeSandbox(tmp_path),
                CAPS,
                RECORD_ID,
            )
        assert invoker.calls == []

    def test_config_without_a_profile_fails_explicitly(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="no provider profile"):
            _runner(RecordingInvoker()).run(
                fix_case(),
                BenchConfig("odd", "m", None, None),
                FakeSandbox(tmp_path),
                CAPS,
                RECORD_ID,
            )


class TestRealInvoker:
    CHILD = [sys.executable, "-c", "import json, os; print(json.dumps(dict(os.environ)))"]

    def test_child_sees_only_the_given_variables(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GH_TOKEN", "must-not-leak")
        result = run_sq_subprocess(self.CHILD, tmp_path, env={"ONLY_THIS": "1"})
        child_env = json.loads(result.stdout)
        assert child_env.get("ONLY_THIS") == "1"
        assert "GH_TOKEN" not in child_env
        assert "PATH" not in child_env

    def test_no_env_still_inherits_for_sq_replay(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GH_TOKEN", "inherited")
        child_env = json.loads(run_sq_subprocess(self.CHILD, tmp_path).stdout)
        assert child_env["GH_TOKEN"] == "inherited"


class TestRegistryAndRequalify:
    def test_runner_is_usable_through_the_protocol(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(case_runners, "_RUNNERS", {})
        invoker = RecordingInvoker()
        register_case_runner(CaseKind.FIX, _runner(invoker))
        runner = case_runner_for(CaseKind.FIX)
        assert runner is not None
        runner.run(fix_case(), CONFIG, FakeSandbox(tmp_path), CAPS, RECORD_ID)
        assert len(invoker.calls) == 1

    def test_a_second_kind_runs_without_touching_the_first(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(case_runners, "_RUNNERS", {})
        fix_invoker, slice_invoker = RecordingInvoker(), RecordingInvoker()
        register_case_runner(CaseKind.FIX, _runner(fix_invoker))
        register_case_runner(CaseKind.SLICE, _runner(slice_invoker))
        slice_runner = case_runner_for(CaseKind.SLICE)
        assert slice_runner is not None
        slice_runner.run(fix_case(), CONFIG, FakeSandbox(tmp_path), CAPS, RECORD_ID)
        assert (len(fix_invoker.calls), len(slice_invoker.calls)) == (0, 1)

    def test_requalify_returns_the_stored_422_result(self, monkeypatch: pytest.MonkeyPatch) -> None:
        stored = object()
        seen: list[tuple[object, ...]] = []

        def fake_qualification_for(*args: object) -> object:
            seen.append(args)
            return stored

        monkeypatch.setattr(case_runners, "qualification_for", fake_qualification_for)
        deps = _FakeDeps()
        case, env = fix_case(), environment()
        result = _runner(RecordingInvoker(), qualify_deps=deps).requalify(case, env)
        assert result is stored
        assert seen == [(case, env, deps.store, deps.repeats)]

    def test_requalify_runs_422_when_nothing_is_stored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        record = qualification()
        candidate = FixCandidate("a" * 40, "b" * 40, NOW, "#7", None, 7)
        qualified: list[tuple[object, object]] = []

        def nothing_stored(*args: object) -> None:
            return None

        monkeypatch.setattr(case_runners, "qualification_for", nothing_stored)

        def fake_qualify_candidate(cand: object, deps: object) -> QualifyResult:
            qualified.append((cand, deps))
            return QualifyResult(record=record)

        monkeypatch.setattr(case_runners, "qualify_candidate", fake_qualify_candidate)
        deps = _FakeDeps()

        def candidate_for(case: BenchmarkCase) -> FixCandidate:
            return candidate

        runner = _runner(RecordingInvoker(), qualify_deps=deps, candidate_for=candidate_for)
        assert runner.requalify(fix_case(), environment()) is record
        assert qualified == [(candidate, deps)]


class _FakeDeps:
    store = object()
    repeats = 3


class TestClassify:
    """The fix runner owns what "the run used the frozen text" means (the case-kind seam)."""

    def _state(self, sha: str) -> RunState:
        return fix_run([fix_context(sha=sha), dispatch(), action("commit")])

    def test_a_run_that_used_the_cases_text_is_committed_when_head_moved(self) -> None:
        case = fix_case()
        sha = hashlib.sha256(case.task_text.encode("utf-8")).hexdigest()
        process = ProcessResult(("sq",), 0, "", "")
        result = _runner(RecordingInvoker()).classify(
            case, process, self._state(sha), "1" * 40, "2" * 40
        )
        assert result.outcome is ProducerOutcome.COMMITTED

    def test_a_run_that_used_other_text_is_a_frozen_text_mismatch(self) -> None:
        process = ProcessResult(("sq",), 0, "", "")
        result = _runner(RecordingInvoker()).classify(
            fix_case(), process, self._state("0" * 64), "1" * 40, "2" * 40
        )
        assert result.outcome is ProducerOutcome.FROZEN_TEXT_MISMATCH

    def test_the_record_names_are_the_fix_pipeline_and_step(self) -> None:
        runner = _runner(RecordingInvoker())
        assert (runner.pipeline, runner.producer_step) == ("fix", "fix")


class TestInstructionFiles:
    def _write(self, tree: Path, relative: str, content: str) -> None:
        path = tree / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def test_a_dangling_symlink_is_recorded_as_unreadable_with_a_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        self._write(tmp_path, "AGENTS.md", "agents")
        (tmp_path / "CLAUDE.md").symlink_to(tmp_path / "missing.md")
        with caplog.at_level(logging.WARNING):
            found = instruction_files(tmp_path)
        assert [path for path, _ in found] == ["AGENTS.md", "CLAUDE.md"]
        assert dict(found)["CLAUDE.md"] == UNREADABLE_MARKER
        assert any("CLAUDE.md" in r.message and r.levelno == logging.WARNING for r in caplog.records)

    def test_a_symlink_out_of_the_tree_is_recorded_with_a_marker_and_a_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        outside = tmp_path / "outside.md"
        outside.write_text("the user's own file")
        tree = tmp_path / "tree"
        tree.mkdir()
        (tree / "CLAUDE.md").symlink_to(outside)
        with caplog.at_level(logging.WARNING):
            assert instruction_files(tree) == (("CLAUDE.md", OUTSIDE_TREE_MARKER),)
        assert any("outside the tree" in r.message for r in caplog.records)

    def test_a_symlink_inside_the_tree_is_hashed_by_its_content(self, tmp_path: Path) -> None:
        import hashlib

        self._write(tmp_path, "AGENTS.md", "shared rules")
        (tmp_path / "CLAUDE.md").symlink_to("AGENTS.md")
        found = dict(instruction_files(tmp_path))
        assert found["CLAUDE.md"] == hashlib.sha256(b"shared rules").hexdigest()

    def test_lists_nested_rule_files_sorted_with_correct_hashes(self, tmp_path: Path) -> None:
        import hashlib

        self._write(tmp_path, "CLAUDE.md", "root")
        self._write(tmp_path, "AGENTS.md", "agents")
        self._write(tmp_path, ".claude/rules/b.md", "b")
        self._write(tmp_path, ".claude/rules/nested/a.md", "a")
        self._write(tmp_path, "sub/CLAUDE.md", "sub")
        found = instruction_files(tmp_path)
        assert [path for path, _ in found] == [
            ".claude/rules/b.md",
            ".claude/rules/nested/a.md",
            "AGENTS.md",
            "CLAUDE.md",
            "sub/CLAUDE.md",
        ]
        assert dict(found)["CLAUDE.md"] == hashlib.sha256(b"root").hexdigest()
        assert dict(found)[".claude/rules/nested/a.md"] == hashlib.sha256(b"a").hexdigest()

    def test_ignores_other_files_and_skipped_directories(self, tmp_path: Path) -> None:
        self._write(tmp_path, "README.md", "x")
        self._write(tmp_path, ".claude/settings.json", "{}")
        self._write(tmp_path, ".claude/rules", "a file named rules")
        self._write(tmp_path, ".venv/lib/pkg/CLAUDE.md", "installed package")
        self._write(tmp_path, ".git/info/AGENTS.md", "metadata")
        self._write(tmp_path, "node_modules/x/AGENTS.md", "dependency")
        assert instruction_files(tmp_path) == ()


class TestIssueRef:
    @pytest.mark.parametrize(
        ("source_ref", "expected"),
        [("#7", (None, 7)), ("owner/repo#42", ("owner/repo", 42)), (" #9 ", (None, 9))],
    )
    def test_parses_the_refs_422_records(
        self, source_ref: str, expected: tuple[str | None, int]
    ) -> None:
        assert parse_issue_ref(source_ref) == expected

    @pytest.mark.parametrize("source_ref", ["", "issue-1", "owner/repo", "#", "#x", "7"])
    def test_unparseable_refs_are_none(self, source_ref: str) -> None:
        assert parse_issue_ref(source_ref) is None
        assert issue_number(fix_case(source_ref)) is None


class TestCandidateFromCase:
    def _repo_with_commit(self, tmp_path: Path) -> tuple[Path, str]:
        env = {
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@t.invalid",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@t.invalid",
            "GIT_COMMITTER_DATE": "2026-01-02T03:04:05+00:00",
            "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        }
        subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True, env=env)
        subprocess.run(
            ["git", "-C", str(tmp_path), "commit", "-q", "--allow-empty", "-m", "fix"],
            check=True,
            env=env,
        )
        sha = subprocess.run(
            ["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True, env=env,
        ).stdout.strip()  # fmt: skip
        return tmp_path, sha

    def test_rebuilds_the_candidate_with_the_committer_date(self, tmp_path: Path) -> None:
        repo, sha = self._repo_with_commit(tmp_path)
        case = fix_case("owner/repo#7").model_copy(update={"reference_sha": sha})
        candidate = candidate_from_case(case, SubprocessRunner(), repo, 30)
        assert candidate == FixCandidate(
            sha=sha,
            parent_sha=case.start_sha,
            committer_date=datetime.fromisoformat("2026-01-02T03:04:05+00:00"),
            issue_ref="owner/repo#7",
            repository="owner/repo",
            number=7,
        )

    def test_unknown_commit_halts_the_build_with_an_error_log(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        from squadron.benchmark.build_errors import BuildHalted

        repo, _ = self._repo_with_commit(tmp_path)
        case = fix_case().model_copy(update={"reference_sha": "f" * 40})
        with caplog.at_level("ERROR"), pytest.raises(BuildHalted):
            candidate_from_case(case, SubprocessRunner(), repo, 30)
        assert any(record.levelname == "ERROR" for record in caplog.records)

    def test_unreadable_ref_halts_the_build(self, tmp_path: Path) -> None:
        from squadron.benchmark.build_errors import BuildHalted

        with pytest.raises(BuildHalted, match="no readable issue ref"):
            candidate_from_case(fix_case("junk"), SubprocessRunner(), tmp_path, 30)
