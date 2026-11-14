"""``replay_one`` end to end against doubles: no model, no cf, no git outside fixtures."""

from __future__ import annotations

import hashlib
import logging
import shutil
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType

import pytest

from squadron.benchmark.adapter import EnvironmentFailureReason, EnvironmentResolutionError
from squadron.benchmark.bench_plan import BenchConfig, Caps
from squadron.benchmark.case_runners import ProducerRun, ReplaySandbox
from squadron.benchmark.leak_rules import LeakRules, build_leak_rules
from squadron.benchmark.replay_one import ReplayOneDeps, ReplayStoreError, replay_one
from squadron.benchmark.replay_outcome import ProducerClassification, classify_producer_run
from squadron.benchmark.transcripts import ToolCall, TranscriptResult
from squadron.core.process_runner import ProcessResult
from squadron.metrology.benchmark_environment import EnvironmentIdentity
from squadron.metrology.benchmark_models import (
    BenchmarkCase,
    CandidateRejection,
    CaseKind,
    FixQualification,
    QualificationOutcome,
)
from squadron.metrology.benchmark_replay_enums import AbsenceClass, LeakVerdict, ProducerOutcome
from squadron.metrology.benchmark_replay_models import CaseDrop, DiffRef, ImplementationReplay
from squadron.metrology.benchmark_store import BenchmarkRecordStore
from squadron.metrology.errors import MetrologyStoreError
from squadron.metrology.replay_models import ProducerConfigRef
from squadron.metrology.store import MetrologyStore
from squadron.pipeline.failure_kind import FailureKind
from squadron.pipeline.state import RunState
from squadron.providers.base import ProfileName
from tests.benchmark.support import Handler, RunnerCall, ScriptedRunner, failed, ok
from tests.benchmark.test_fix_case_runner import fix_case
from tests.benchmark.test_replay_outcome import dispatch, fix_context, fix_run
from tests.metrology.test_benchmark_models import environment, qualification
from tests.stats.producer_support import action, prompt_identity

BEFORE, AFTER = "1" * 40, "2" * 40
CONFIG = BenchConfig("opus", "claude-opus-5-5", "sdk", "high")
CAPS = Caps(40.0, 1.5, "--max-cost-per-replay")
NOW = datetime(2026, 11, 14, 12, tzinfo=UTC)
DIFF = "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-a\n+b\n"
RECORD_LIMIT_BYTES = 8 * 1024
CASE_SHA = hashlib.sha256(fix_case().task_text.encode("utf-8")).hexdigest()


def ctx(sha: str = CASE_SHA, *, success: bool = True) -> dict[str, object]:
    """A ``fix-context`` action that used the case's frozen text, unless *sha* says otherwise."""
    return fix_context(sha=sha, success=success)


class FakeSandbox:
    def __init__(self, root: Path, digest_seed: str) -> None:
        self.tree, self.home, self.output_dir = root / "tree", root / "home", root / "out"
        for directory in (self.tree, self.home, self.output_dir):
            directory.mkdir(parents=True)
        self.identity = environment(digest_seed)
        self.kept = False
        self.removed = False

    def keep(self) -> None:
        self.kept = True

    def producer_env(self, profile: ProfileName) -> dict[str, str]:
        raise AssertionError("the runner double never asks for a producer environment")

    def checkout_branch(self, name: str) -> None:
        raise AssertionError("the runner double never checks out a branch")

    def __enter__(self) -> FakeSandbox:
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        self.removed = not self.kept
        if self.removed:
            shutil.rmtree(self.tree.parent, ignore_errors=True)


class Factory:
    def __init__(self, root: Path, *, digest_seed: str = "l" * 64) -> None:
        self._root, self.digest_seed = root, digest_seed
        self.sandboxes: list[FakeSandbox] = []
        self.failure: Exception | None = None
        #: Called on each new sandbox, to put files in its tree before the replay starts.
        self.on_create: Callable[[FakeSandbox], None] | None = None

    def __call__(self, case: BenchmarkCase) -> FakeSandbox:
        if self.failure is not None:
            raise self.failure
        sandbox = FakeSandbox(self._root / f"sandbox-{len(self.sandboxes)}", self.digest_seed)
        self.sandboxes.append(sandbox)
        if self.on_create is not None:
            self.on_create(sandbox)
        return sandbox


class FakeRunner:
    pipeline = "fix"
    producer_step = "fix"

    def __init__(
        self, qualified: FixQualification | CandidateRejection, process: ProcessResult | None = None
    ) -> None:
        self.qualified = qualified
        self.requalified = 0
        self.runs = 0
        self._process = process or ProcessResult(("sq",), 0, "", "")
        #: Called with the sandbox just before the producer "runs", to act as the producer.
        self.before_run: Callable[[ReplaySandbox], None] | None = None

    def requalify(
        self, case: BenchmarkCase, environment: EnvironmentIdentity
    ) -> FixQualification | CandidateRejection:
        self.requalified += 1
        return self.qualified

    def run(
        self,
        case: BenchmarkCase,
        config: BenchConfig,
        sandbox: ReplaySandbox,
        caps: Caps,
        record_id: str,
    ) -> ProducerRun:
        self.runs += 1
        if self.before_run is not None:
            self.before_run(sandbox)
        return self._process

    def classify(
        self,
        case: BenchmarkCase,
        process: ProcessResult,
        state: RunState | None,
        head_before: str,
        head_after: str,
    ) -> ProducerClassification:
        issue_sha256 = hashlib.sha256(case.task_text.encode("utf-8")).hexdigest()
        return classify_producer_run(process, state, head_before, head_after, issue_sha256)


class Source:
    def __init__(self, *commands: str) -> None:
        calls = tuple(ToolCall("Bash", {"command": c}) for c in commands)
        self._result = TranscriptResult(tool_calls=calls, files_read=1)

    def read(self, home: Path) -> TranscriptResult:
        return self._result


class Reader:
    def __init__(self, state: RunState | None) -> None:
        self._state = state

    def load(self, run_id: str) -> RunState:
        if self._state is None:
            raise FileNotFoundError(run_id)
        return self._state


class World:
    """Everything one replay needs, with knobs for each double."""

    def __init__(self, tmp_path: Path) -> None:
        self.tmp_path = tmp_path
        self.store = BenchmarkRecordStore(MetrologyStore(store_dir=tmp_path / "store"))
        self.factory = Factory(tmp_path)
        self.runner = FakeRunner(qualification())
        self.state: RunState | None = fix_run([ctx(), dispatch(), action("commit")])
        self.source = Source("ls", "cat hello.txt")
        self.heads = [BEFORE, AFTER]
        self.diff_result: ProcessResult | None = None
        #: Replaceable by a test; the scripted runner calls whatever is set when it is asked.
        self.git_handler: Handler = self._git
        self.git = ScriptedRunner(lambda call: self.git_handler(call))
        self.keep = False
        self.requalify_cache: dict[tuple[str, str], FixQualification | CandidateRejection] = {}
        self.config_ref = ProducerConfigRef(
            alias="opus", model="claude-opus-5-5", profile="sdk", effort_sent=None, tool_use=True
        )

    def _git(self, call: RunnerCall) -> ProcessResult:
        if call.argv[1] == "rev-parse":
            return ok(call.argv, self.heads.pop(0) + "\n")
        return self.diff_result or ok(call.argv, DIFF)

    def deps(self) -> ReplayOneDeps:
        def rules(sandbox: ReplaySandbox, case: BenchmarkCase) -> LeakRules:
            return build_leak_rules(
                tree=sandbox.tree,
                home=sandbox.home,
                output_dir=sandbox.output_dir,
                real_home=self.tmp_path / "real-home",
                repo_root=self.tmp_path / "checkout",
                install_location=self.tmp_path / "site",
                uv_cache=self.tmp_path / "uvcache",
                distribution_name="squadron-ai",
                host_owner="owner",
                host_repo="repo",
            )

        return ReplayOneDeps(
            benchmark_id="bench-0123456789abcdef",
            case_set="fixes",
            case_set_version=1,
            caps=CAPS,
            keep=self.keep,
            git_timeout_s=30,
            sandbox_factory=self.factory,
            runners=lambda kind: self.runner if kind is CaseKind.FIX else None,
            store=self.store,
            state_reader_for=lambda runs_dir: Reader(self.state),
            transcript_sources=lambda profile: self.source,
            leak_rules_for=rules,
            config_ref_for=lambda config: self.config_ref,
            process_runner=self.git,
            clock=lambda: NOW,
            requalify_cache=self.requalify_cache,
        )

    def replay(self, sample: int = 0) -> ImplementationReplay | CaseDrop:
        return replay_one(fix_case(), CONFIG, sample, self.deps())


@pytest.fixture
def world(tmp_path: Path) -> World:
    return World(tmp_path)


def committed(world: World) -> ImplementationReplay:
    record = world.replay()
    assert isinstance(record, ImplementationReplay)
    return record


class TestCommitted:
    def test_record_carries_the_run_the_diff_and_the_environment(self, world: World) -> None:
        identity = prompt_identity(None)
        world.state = fix_run(
            [
                ctx(),
                dispatch(prompt_identity=identity, effort_stamp="high"),
                action("commit"),
            ]
        )
        record = committed(world)
        assert record.outcome == ProducerOutcome.COMMITTED
        assert record.absence is None
        assert record.commit_sha == AFTER
        assert record.diff is not None and record.diff.bytes == len(DIFF.encode())
        assert record.diff.files_changed == 1
        assert world.store.diffs.get(record.diff.sha256) == DIFF.encode()
        assert record.environment == world.factory.sandboxes[0].identity
        assert record.prompt is not None and record.prompt.sha256 == identity["sha256"]
        assert record.cost_usd is not None and abs(record.cost_usd - 0.4) < 1e-9
        assert record.turns == 1
        assert record.config.effort_sent == "high"
        assert record.leak is not None and record.leak.verdict == LeakVerdict.NO_LEAK_DETECTED
        assert record.pipeline == "fix" and record.producer_step == "fix"
        assert record.created_at == NOW

    def test_instruction_files_present_at_the_start_are_recorded(self, world: World) -> None:
        def seed(sandbox: FakeSandbox) -> None:
            (sandbox.tree / "CLAUDE.md").write_text("root rules")
            (sandbox.tree / ".claude" / "rules").mkdir(parents=True)
            (sandbox.tree / ".claude" / "rules" / "a.md").write_text("a")

        world.factory.on_create = seed
        record = committed(world)
        assert [path for path, _ in record.instruction_files] == [".claude/rules/a.md", "CLAUDE.md"]

    def test_files_the_producer_adds_are_not_recorded(self, world: World) -> None:
        def write_rule(sandbox: ReplaySandbox) -> None:
            (sandbox.tree / "CLAUDE.md").write_text("added by the producer")

        world.runner.before_run = write_rule
        assert committed(world).instruction_files == ()

    def test_record_is_under_8_kb(self, world: World) -> None:
        record = committed(world)
        assert len(record.model_dump_json().encode()) < RECORD_LIMIT_BYTES

    def test_the_record_is_stored_under_its_id(self, world: World) -> None:
        record = committed(world)
        assert world.store.get_replay(record.run_id) == record
        assert record.run_id.startswith("implreplay-0123456789ab-")

    def test_empty_diff_with_moved_head_is_committed_with_a_zero_byte_ref(self, world: World) -> None:
        world.diff_result = ok(("git", "diff"), "")
        record = committed(world)
        assert record.outcome == ProducerOutcome.COMMITTED
        assert record.diff is not None and (record.diff.bytes, record.diff.files_changed) == (0, 0)

    def test_sandbox_is_removed_after_success(self, world: World) -> None:
        committed(world)
        assert world.factory.sandboxes[0].removed

    def test_keep_leaves_the_sandbox_after_a_written_record(self, world: World) -> None:
        world.keep = True
        committed(world)
        assert world.factory.sandboxes[0].kept and not world.factory.sandboxes[0].removed


class TestOutcomes:
    def _replay_state(
        self, world: World, state: RunState | None, *, heads: list[str] | None = None
    ) -> ImplementationReplay:
        world.state = state
        world.heads = heads if heads is not None else [BEFORE, BEFORE]
        record = world.replay()
        assert isinstance(record, ImplementationReplay)
        return record

    def test_cost_cap(self, world: World) -> None:
        capped = dispatch(success=False, error="budget", failure_kind=FailureKind.COST_CAP.value)
        record = self._replay_state(world, fix_run([ctx(), capped], status="failed"))
        assert (record.outcome, record.absence) == (ProducerOutcome.COST_CAP, AbsenceClass.CONFIG)
        assert record.diff is None and record.commit_sha is None

    def test_blocked(self, world: World) -> None:
        asking = action("dispatch", success=False, error="BLOCKED: decide")
        asking["awaits_human"] = True
        record = self._replay_state(world, fix_run([ctx(), asking], status="paused"))
        assert (record.outcome, record.absence) == (ProducerOutcome.BLOCKED, AbsenceClass.CONFIG)

    def test_no_commit_via_a_fix_report_refusal(self, world: World) -> None:
        refusal = action(
            "commit", success=False, error="no fix report", failure_kind=FailureKind.FIX_REPORT.value
        )
        state = fix_run([ctx(), dispatch(), refusal], status="failed")
        record = self._replay_state(world, state)
        assert (record.outcome, record.absence) == (ProducerOutcome.NO_COMMIT, AbsenceClass.CONFIG)

    def test_producer_failed_via_stall(self, world: World) -> None:
        stalled = dispatch(success=False, error="no output", failure_kind=FailureKind.STALL.value)
        record = self._replay_state(world, fix_run([ctx(), stalled], status="failed"))
        assert record.outcome == ProducerOutcome.PRODUCER_FAILED
        assert "stall" in (record.failure_detail or "")

    def test_no_run_state_when_the_process_was_killed(self, world: World) -> None:
        world.runner = FakeRunner(qualification(), ProcessResult(("sq",), -9, "", "Killed"))
        record = self._replay_state(world, None)
        assert (record.outcome, record.absence) == (ProducerOutcome.NO_RUN_STATE, AbsenceClass.HARNESS)
        assert "Killed" in (record.failure_detail or "")

    def test_frozen_text_mismatch(self, world: World) -> None:
        state = fix_run([ctx("f" * 64), dispatch(), action("commit")])
        record = self._replay_state(world, state, heads=[BEFORE, AFTER])
        assert (record.outcome, record.absence) == (
            ProducerOutcome.FROZEN_TEXT_MISMATCH,
            AbsenceClass.HARNESS,
        )
        assert record.diff is not None  # HEAD moved: stored for inspection

    def test_environment_failure_records_harness_absence_and_runs_no_producer(
        self, world: World
    ) -> None:
        world.factory.failure = EnvironmentResolutionError(
            EnvironmentFailureReason.LOCK_STALE_OR_UNRESOLVABLE, "uv sync failed"
        )
        record = world.replay()
        assert isinstance(record, ImplementationReplay)
        assert (record.outcome, record.absence) == (
            ProducerOutcome.ENVIRONMENT_FAILED,
            AbsenceClass.HARNESS,
        )
        assert "uv sync failed" in (record.failure_detail or "")
        assert (record.leak, record.diff, record.environment) == (None, None, None)
        assert world.runner.runs == 0
        assert world.store.get_replay(record.run_id) == record


class TestLeak:
    def test_leaked_transcript_on_a_committed_run_is_a_harness_absence_with_the_diff_kept(
        self, world: World
    ) -> None:
        world.source = Source("gh issue view 3")
        record = committed(world)
        assert record.outcome == ProducerOutcome.COMMITTED
        assert record.absence == AbsenceClass.HARNESS
        assert record.leak is not None and record.leak.verdict == LeakVerdict.LEAKED
        assert record.diff is not None
        assert "leaked" in (record.failure_detail or "")

    def test_scan_unavailable_is_a_harness_absence_too(self, world: World) -> None:
        world.source = Source()
        record = committed(world)
        assert record.outcome == ProducerOutcome.COMMITTED
        assert record.absence == AbsenceClass.HARNESS
        assert record.leak is not None and record.leak.verdict == LeakVerdict.SCAN_UNAVAILABLE
        assert record.diff is not None

    def test_a_config_absence_with_a_clean_scan_stays_config(self, world: World) -> None:
        world.heads = [BEFORE, BEFORE]
        record = world.replay()
        assert isinstance(record, ImplementationReplay)
        assert record.absence == AbsenceClass.CONFIG  # completed, HEAD unchanged


class TestRequalification:
    def test_rejection_returns_a_case_drop_and_dispatches_nothing(self, world: World) -> None:
        world.runner = FakeRunner(CandidateRejection.NO_TEST_CHANGE)
        result = world.replay()
        assert isinstance(result, CaseDrop)
        assert result.reason == CandidateRejection.NO_TEST_CHANGE
        assert result.environment_digest == world.factory.sandboxes[0].identity.identity_digest
        assert world.runner.runs == 0
        assert world.git.calls == []
        assert world.factory.sandboxes[0].removed
        assert world.store.replays_for("bench-0123456789abcdef") == []

    def test_a_qualification_that_is_not_qualified_is_a_drop_with_its_reason(
        self, world: World
    ) -> None:
        rejected = qualification(
            outcome=QualificationOutcome.REJECTED,
            case_id=None,
            rejection=CandidateRejection.COLLECTION_FAILED,
        )
        world.runner = FakeRunner(rejected)
        result = world.replay()
        assert isinstance(result, CaseDrop) and result.reason == CandidateRejection.COLLECTION_FAILED

    def test_a_harness_error_qualification_drops_with_its_detail(self, world: World) -> None:
        errored = qualification(
            outcome=QualificationOutcome.HARNESS_ERROR, case_id=None, detail="uv exploded"
        )
        world.runner = FakeRunner(errored)
        result = world.replay()
        assert isinstance(result, CaseDrop) and result.reason == "uv exploded"

    def test_two_replays_in_one_environment_requalify_once(self, world: World) -> None:
        world.heads = [BEFORE, AFTER, BEFORE, AFTER]
        world.replay(0)
        world.replay(1)
        assert world.runner.requalified == 1
        assert world.runner.runs == 2

    def test_a_different_environment_digest_requalifies_again(self, world: World) -> None:
        world.heads = [BEFORE, AFTER, BEFORE, AFTER]
        world.replay(0)
        world.factory.digest_seed = "z" * 64
        world.replay(1)
        assert world.runner.requalified == 2


class TestStoreFailures:
    def test_git_diff_failure_raises_logs_error_keeps_the_sandbox_and_writes_nothing(
        self, world: World, caplog: pytest.LogCaptureFixture
    ) -> None:
        world.diff_result = failed(("git", "diff"), 128, "fatal: bad object")
        with (
            caplog.at_level(logging.ERROR),
            pytest.raises(ReplayStoreError, match="git diff exited 128"),
        ):
            world.replay()
        assert any(r.levelno == logging.ERROR and "bad object" in r.message for r in caplog.records)
        assert world.factory.sandboxes[0].kept
        assert world.store.replays_for("bench-0123456789abcdef") == []

    def test_sidecar_write_failure_raises_keeps_the_sandbox_and_writes_nothing(
        self, world: World, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def boom(data: bytes) -> DiffRef:
            raise MetrologyStoreError("disk full")

        monkeypatch.setattr(world.store.diffs, "put", boom)
        with pytest.raises(ReplayStoreError, match="disk full"):
            world.replay()
        assert world.factory.sandboxes[0].kept
        assert world.store.replays_for("bench-0123456789abcdef") == []

    def test_record_write_failure_raises_and_keeps_the_sandbox(
        self, world: World, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        def boom(record_id: str, replay: ImplementationReplay) -> str:
            raise MetrologyStoreError("read-only store")

        monkeypatch.setattr(world.store, "write_replay", boom)
        with caplog.at_level(logging.ERROR), pytest.raises(ReplayStoreError, match="read-only store"):
            world.replay()
        assert world.factory.sandboxes[0].kept
        assert any(r.levelno == logging.ERROR for r in caplog.records)

    def test_unreadable_head_after_the_producer_raises_and_keeps_the_sandbox(
        self, world: World
    ) -> None:
        calls = {"n": 0}
        original = world.git_handler

        def handler(call: RunnerCall) -> ProcessResult:
            if call.argv[1] == "rev-parse":
                calls["n"] += 1
                if calls["n"] == 2:
                    return failed(call.argv, 128, "fatal")
            return original(call)

        world.git_handler = handler
        with pytest.raises(ReplayStoreError, match="after the producer"):
            world.replay()
        assert world.factory.sandboxes[0].kept

    def test_unreadable_head_before_the_producer_is_an_environment_failure(self, world: World) -> None:
        world.git_handler = lambda call: failed(call.argv, 128, "fatal: not a repo")
        record = world.replay()
        assert isinstance(record, ImplementationReplay)
        assert record.outcome == ProducerOutcome.ENVIRONMENT_FAILED
        assert world.runner.runs == 0
