"""Sandbox qualification stages through test-first, with a scripted adapter (slice 422)."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Any

import pytest

from squadron.benchmark import qualify_sandbox
from squadron.benchmark.adapter import (
    EnvironmentFailureReason,
    EnvironmentResolutionError,
    FailureKind,
    NodeOutcome,
    NodeResult,
    SandboxContext,
    SuiteRun,
    SuiteRunError,
    SuiteSelection,
)
from squadron.benchmark.diff_classify import DiffClassification
from squadron.benchmark.fairness import (
    FAIRNESS_RULE_VERSION,
    AllowedBoundary,
    BoundaryUndecidable,
    CollectedTests,
    CollectionFailed,
    FairnessVerdict,
    HarnessFailure,
)
from squadron.benchmark.fix_discovery import FixCandidate
from squadron.benchmark.qualify_sandbox import qualify_in_sandbox
from squadron.benchmark.qualify_types import QualifyDeps, QualifyResult
from squadron.benchmark.scrubbed_env import MissingHarnessHomeError
from squadron.metrology.benchmark_environment import EnvironmentIdentity
from squadron.metrology.benchmark_models import (
    CandidateRejection,
    FixQualification,
    HiddenTestVerdictKind,
    QualificationOutcome,
    TestRejection,
)
from squadron.metrology.benchmark_store import BenchmarkRecordStore
from squadron.metrology.project_id import ProjectId, ProjectIdSource
from squadron.metrology.snapshot_models import SourceLanguage
from squadron.metrology.store import MetrologyStore
from squadron.replay.history_free_sandbox import SandboxError
from tests.benchmark.support import RunnerCall, ScriptedRunner, bare_context

PARENT = "p" * 40
FIX = "f" * 40
PROJECT = ProjectId(value="proj", source=ProjectIdSource.RECORDED)
CANDIDATE = FixCandidate(FIX, PARENT, datetime(2026, 10, 10, tzinfo=UTC), "#5", None, 5)
CLASSIFICATION = DiffClassification(
    added=("tests/test_new.py",),
    changed=("src/pkg/mod.py",),
    deleted=(),
    test_side=("tests/test_new.py",),
)
HIDDEN_A = "tests/test_new.py::test_a"
HIDDEN_B = "tests/test_new.py::test_b"
ALLOWED = AllowedBoundary(frozenset({("pkg", "api")}))


def environment(lock_hash: str = "l" * 64) -> EnvironmentIdentity:
    return EnvironmentIdentity(
        language=SourceLanguage.PYTHON,
        lockfile_path="uv.lock",
        lockfile_sha256=lock_hash,
        interpreter_version="3.12.1",
        installer_version="uv 0.5",
        platform="darwin-arm64",
        scrub_spec_version=1,
    )


def collected(*node_ids: str) -> CollectedTests:
    return CollectedTests(
        digests={node: "digest" for node in node_ids}, fixtures_reached={}, conftest_fixtures=()
    )


class ScriptedAdapter:
    """A ``FixCaseAdapter`` whose answers are scripted; every call lands in ``log``."""

    language = SourceLanguage.PYTHON
    project_config_name = "pyproject.toml"

    def __init__(self, log: list[str]) -> None:
        self.log = log
        self.collections: list[CollectedTests | Exception] = [
            collected("old"),
            collected("old", HIDDEN_A, HIDDEN_B),
        ]
        self.allowed: AllowedBoundary | Exception = ALLOWED
        self.traced: dict[str, FairnessVerdict] | Exception = {
            HIDDEN_A: FairnessVerdict(None),
            HIDDEN_B: FairnessVerdict(None),
        }
        self.overlay_failure: Exception | None = None

    def is_test_side(self, pyproject_text: str | None, path: str) -> bool:
        return path.startswith("tests/")

    def is_test_source(self, path: str) -> bool:
        return path.endswith(".py")

    def lockfile_names(self) -> tuple[str, ...]:
        return ("uv.lock",)

    def collect(self, ctx: SandboxContext) -> CollectedTests:
        self.log.append("collect")
        step = self.collections.pop(0)
        if isinstance(step, Exception):
            raise step
        return step

    def overlay(self, ctx: SandboxContext, files: Mapping[str, bytes | None]) -> None:
        # Absent files (None) say nothing about the state; the first byte is the source sha letter.
        contents = {content[:1] for content in files.values() if content}
        label = {frozenset({b"f"}): "reference", frozenset({b"p"}): "parent"}.get(
            frozenset(contents), "parent+overlay"
        )
        self.log.append(f"overlay:{label}")
        if self.overlay_failure is not None:
            raise self.overlay_failure

    def boundary(self, ctx: SandboxContext) -> AllowedBoundary:
        self.log.append("boundary")
        if isinstance(self.allowed, Exception):
            raise self.allowed
        return self.allowed

    def trace(
        self, ctx: SandboxContext, node_ids: Sequence[str], allowed: AllowedBoundary
    ) -> Mapping[str, FairnessVerdict]:
        self.log.append("trace")
        if isinstance(self.traced, Exception):
            raise self.traced
        return {node: self.traced[node] for node in node_ids}

    def grader_commands(self, tree: Path) -> tuple[Any, ...]:
        return ()


class ScriptedSuites:
    def __init__(self, log: list[str]) -> None:
        self.log = log
        self.script: list[SuiteRun | Exception] = []
        self.default = {
            node: NodeResult(node, NodeOutcome.FAILED, FailureKind.ASSERTION_FAILURE)
            for node in (HIDDEN_A, HIDDEN_B)
        }

    def run_suite(self, ctx: SandboxContext, selection: SuiteSelection) -> SuiteRun:
        self.log.append("suite")
        if self.script:
            step = self.script.pop(0)
            if isinstance(step, Exception):
                raise step
            return step
        assert selection.node_ids is not None
        return SuiteRun(results=tuple(self.default[node] for node in selection.node_ids))


class FakeSandbox:
    def __init__(self, tmp_path: Path, identity: EnvironmentIdentity) -> None:
        self.identity = identity
        self._context = bare_context(tmp_path)

    def context(self) -> SandboxContext:
        return self._context


class SandboxHandle:
    def __init__(self, sandbox: FakeSandbox, enter_error: Exception | None) -> None:
        self._sandbox = sandbox
        self._enter_error = enter_error
        self.exited = False

    def __enter__(self) -> FakeSandbox:
        if self._enter_error is not None:
            raise self._enter_error
        return self._sandbox

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        self.exited = True


@dataclass
class World:
    deps: QualifyDeps
    adapter: ScriptedAdapter
    suites: ScriptedSuites
    store: BenchmarkRecordStore
    log: list[str]
    handles: list[SandboxHandle] = field(default_factory=list)
    survivors_calls: list[tuple[Any, ...]] = field(default_factory=list)


def world(
    tmp_path: Path, *, identity: EnvironmentIdentity | None = None, enter_error: Exception | None = None
) -> World:
    log: list[str] = []
    adapter = ScriptedAdapter(log)
    suites = ScriptedSuites(log)
    store = BenchmarkRecordStore(MetrologyStore(store_dir=tmp_path / "store"))
    handles: list[SandboxHandle] = []
    fake = FakeSandbox(tmp_path, identity or environment())

    def factory(start_sha: str) -> SandboxHandle:
        assert start_sha == PARENT
        handle = SandboxHandle(fake, enter_error)
        handles.append(handle)
        return handle

    def git(call: RunnerCall) -> Any:
        from squadron.core.process_runner import ProcessResult

        sha, _, path = call.argv[2].partition(":")
        return ProcessResult(call.argv, 0, f"{sha[0]}:{path}", "")

    deps = QualifyDeps(
        repo_root=tmp_path,
        project_id=PROJECT,
        host=_unused_host(),
        store=store,
        runner=ScriptedRunner(git),
        adapter=adapter,
        sandbox_stages=qualify_in_sandbox,
        sandbox_factory=factory,
        suite_runner=suites,
        repeats=2,
        git_timeout_seconds=30,
    )
    return World(deps, adapter, suites, store, log, handles)


def _unused_host() -> Any:
    class Host:
        pass

    return Host()


@pytest.fixture
def survivors_hook(monkeypatch: pytest.MonkeyPatch) -> Callable[[World], None]:
    """Replace stage 7 with a recorder: this file tests the stages before it."""

    def install(setup: World) -> None:
        def fake(*args: Any) -> QualifyResult:
            setup.log.append("survivors")
            setup.survivors_calls.append(args)
            return QualifyResult(_qualified_record(args[-1]))

        monkeypatch.setattr(qualify_sandbox, "qualify_survivors", fake)

    return install


def _qualified_record(deps: QualifyDeps) -> FixQualification:
    return FixQualification(
        project_id=PROJECT,
        commit_sha=FIX,
        parent_sha=PARENT,
        issue_ref="#5",
        rule_version=FAIRNESS_RULE_VERSION,
        environment=environment(),
        repeats=deps.repeats,
        outcome=QualificationOutcome.QUALIFIED,
        case_id="case-0000000000000000",
        created_at=datetime.now(UTC),
    )


def run(setup: World) -> QualifyResult:
    return qualify_in_sandbox(CANDIDATE, CLASSIFICATION, "task text", setup.deps)


# --- Stage order and early exit ----------------------------------------------------------


def test_the_full_path_calls_each_stage_in_order_at_the_right_file_state(
    tmp_path: Path, survivors_hook: Callable[[World], None]
) -> None:
    setup = world(tmp_path)
    survivors_hook(setup)
    run(setup)
    assert setup.log == [
        "collect",
        "boundary",
        "overlay:reference",
        "collect",
        "trace",
        "overlay:parent+overlay",
        "suite",
        "suite",
        "survivors",
    ]
    assert setup.handles[0].exited


def test_survivors_get_the_sets_verdicts_and_task_text(
    tmp_path: Path, survivors_hook: Callable[[World], None]
) -> None:
    setup = world(tmp_path)
    survivors_hook(setup)
    run(setup)
    sandbox, candidate, task_text, sets, verdicts, states, deps = setup.survivors_calls[0]
    assert candidate is CANDIDATE and task_text == "task text" and deps is setup.deps
    assert sets.hidden_candidates == (HIDDEN_A, HIDDEN_B)
    assert [v.kind for v in verdicts] == [HiddenTestVerdictKind.QUALIFIED] * 2
    assert states.reference_files


def test_collection_failure_at_the_parent_ends_the_candidate(tmp_path: Path) -> None:
    setup = world(tmp_path)
    setup.adapter.collections = [CollectionFailed("tests/test_old.py", "SyntaxError")]
    result = run(setup)
    assert result.record.rejection is CandidateRejection.COLLECTION_FAILED
    assert "at the parent" in result.record.detail
    assert setup.log == ["collect"]
    assert result.record.environment == environment()


def test_an_undecidable_boundary_is_a_rejection_not_a_harness_error(tmp_path: Path) -> None:
    setup = world(tmp_path)
    setup.adapter.allowed = BoundaryUndecidable("ImportError: nope")
    result = run(setup)
    assert result.record.outcome is QualificationOutcome.REJECTED
    assert result.record.rejection is CandidateRejection.BOUNDARY_UNDECIDABLE
    assert setup.log == ["collect", "boundary"]


def test_an_empty_boundary_is_no_packaging_boundary(tmp_path: Path) -> None:
    setup = world(tmp_path)
    setup.adapter.allowed = AllowedBoundary()
    assert run(setup).record.rejection is CandidateRejection.NO_PACKAGING_BOUNDARY
    assert setup.log == ["collect", "boundary"]


def test_collection_failure_at_the_reference_ends_the_candidate(tmp_path: Path) -> None:
    setup = world(tmp_path)
    setup.adapter.collections = [collected("old"), CollectionFailed("tests/test_new.py", "boom")]
    result = run(setup)
    assert result.record.rejection is CandidateRejection.COLLECTION_FAILED
    assert "at the reference" in result.record.detail
    assert setup.log == ["collect", "boundary", "overlay:reference", "collect"]


def test_a_fix_that_adds_no_test_has_no_qualifying_hidden_test(tmp_path: Path) -> None:
    setup = world(tmp_path)
    setup.adapter.collections = [collected("old"), collected("old")]
    result = run(setup)
    assert result.record.rejection is CandidateRejection.NO_QUALIFYING_HIDDEN_TEST
    assert "trace" not in setup.log


def test_trace_rejections_skip_test_first_when_none_survive(tmp_path: Path) -> None:
    setup = world(tmp_path)
    setup.adapter.traced = {
        HIDDEN_A: FairnessVerdict(TestRejection.PATCHES_PROJECT_CODE, "pkg.mod.run"),
        HIDDEN_B: FairnessVerdict(TestRejection.REACHES_PAST_BOUNDARY, "pkg.internal.f"),
    }
    result = run(setup)
    assert result.record.rejection is CandidateRejection.NO_QUALIFYING_HIDDEN_TEST
    assert "suite" not in setup.log and "overlay:parent+overlay" not in setup.log
    reasons = {v.node_id: (v.rejection, v.detail) for v in result.record.hidden_verdicts}
    assert reasons == {
        HIDDEN_A: (TestRejection.PATCHES_PROJECT_CODE, "pkg.mod.run"),
        HIDDEN_B: (TestRejection.REACHES_PAST_BOUNDARY, "pkg.internal.f"),
    }


def test_verdicts_combine_trace_rejections_first_then_test_first(
    tmp_path: Path, survivors_hook: Callable[[World], None]
) -> None:
    setup = world(tmp_path)
    survivors_hook(setup)
    setup.adapter.traced = {
        HIDDEN_A: FairnessVerdict(TestRejection.PATCHES_PROJECT_CODE, "pkg.mod.run"),
        HIDDEN_B: FairnessVerdict(None),
    }
    run(setup)
    verdicts = setup.survivors_calls[0][4]
    assert [(v.node_id, v.kind, v.rejection) for v in verdicts] == [
        (HIDDEN_A, HiddenTestVerdictKind.REJECTED, TestRejection.PATCHES_PROJECT_CODE),
        (HIDDEN_B, HiddenTestVerdictKind.QUALIFIED, None),
    ]
    assert setup.log.count("suite") == 2  # only the survivor ran, twice


def test_test_first_rejections_are_recorded_when_every_survivor_fails_them(tmp_path: Path) -> None:
    setup = world(tmp_path)
    setup.suites.default = {
        HIDDEN_A: NodeResult(HIDDEN_A, NodeOutcome.PASSED),
        HIDDEN_B: NodeResult(HIDDEN_B, NodeOutcome.ERROR, FailureKind.MISSING_SYMBOL),
    }
    result = run(setup)
    assert result.record.rejection is CandidateRejection.NO_QUALIFYING_HIDDEN_TEST
    assert [v.rejection for v in result.record.hidden_verdicts] == [
        TestRejection.PASSES_AT_PARENT,
        TestRejection.USES_SYMBOL_ADDED_BY_FIX,
    ]


# --- Reuse (D10) ------------------------------------------------------------------------


def stored(setup: World, **changes: Any) -> FixQualification:
    base: dict[str, Any] = {
        "project_id": PROJECT,
        "commit_sha": FIX,
        "parent_sha": PARENT,
        "issue_ref": "#5",
        "rule_version": FAIRNESS_RULE_VERSION,
        "environment": environment(),
        "repeats": 2,
        "outcome": QualificationOutcome.QUALIFIED,
        "case_id": "case-1111111111111111",
        "created_at": datetime.now(UTC),
    }
    record = FixQualification(**{**base, **changes})
    setup.store.write_fix_qualification(record)
    return record


def test_a_matching_record_is_reused_without_running_anything_past_the_sandbox(tmp_path: Path) -> None:
    setup = world(tmp_path)
    record = stored(setup)
    result = run(setup)
    assert result.reused is True
    assert result.record == record
    assert setup.log == []
    # The reuse key includes the environment digest, so the sandbox (and its environment) is
    # built even for a reused candidate; this pins that documented cost.
    assert len(setup.handles) == 1
    assert setup.handles[0].exited


@pytest.mark.parametrize(
    "changes",
    [
        {"rule_version": FAIRNESS_RULE_VERSION + 1},
        {"outcome": QualificationOutcome.HARNESS_ERROR, "case_id": None},
        {"repeats": 3},
    ],
    ids=["other rule version", "harness error", "other repeat count"],
)
def test_records_that_must_not_be_reused_requalify(
    tmp_path: Path, survivors_hook: Callable[[World], None], changes: dict[str, Any]
) -> None:
    setup = world(tmp_path)
    survivors_hook(setup)
    stored(setup, **changes)
    result = run(setup)
    assert result.reused is False
    assert setup.log[0] == "collect"


def test_a_record_for_another_environment_digest_requalifies(
    tmp_path: Path, survivors_hook: Callable[[World], None]
) -> None:
    setup = world(tmp_path)
    survivors_hook(setup)
    stored(setup, environment=environment("m" * 64))
    result = run(setup)
    assert result.reused is False
    assert setup.log[0] == "collect"


# --- Harness failures --------------------------------------------------------------------


def assert_harness_error(result: QualifyResult, caplog: pytest.LogCaptureFixture, text: str) -> None:
    assert result.record.outcome is QualificationOutcome.HARNESS_ERROR
    assert result.record.rejection is None
    assert text in result.record.detail
    assert any(record.levelno == logging.ERROR for record in caplog.records)


def test_a_collect_failure_is_a_harness_error(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    setup = world(tmp_path)
    setup.adapter.collections = [HarnessFailure("pytest timed out")]
    with caplog.at_level(logging.ERROR):
        result = run(setup)
    assert_harness_error(result, caplog, "pytest timed out")
    assert result.record.environment == environment()


def test_a_boundary_failure_is_a_harness_error(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    setup = world(tmp_path)
    setup.adapter.allowed = HarnessFailure("resolver crashed")
    with caplog.at_level(logging.ERROR):
        assert_harness_error(run(setup), caplog, "resolver crashed")


def test_a_trace_failure_is_a_harness_error(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    setup = world(tmp_path)
    setup.adapter.traced = HarnessFailure("trace output missing")
    with caplog.at_level(logging.ERROR):
        assert_harness_error(run(setup), caplog, "trace output missing")


def test_a_file_state_switch_failure_is_a_harness_error(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    setup = world(tmp_path)
    setup.adapter.overlay_failure = HarnessFailure("overlay of tests/test_new.py failed")
    with caplog.at_level(logging.ERROR):
        assert_harness_error(run(setup), caplog, "overlay of tests/test_new.py failed")


def test_a_suite_run_error_is_a_harness_error(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    setup = world(tmp_path)
    setup.suites.script = [SuiteRunError("pytest exited 3; stderr: boom")]
    with caplog.at_level(logging.ERROR):
        assert_harness_error(run(setup), caplog, "boom")


def test_a_suite_timeout_is_a_harness_error(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    setup = world(tmp_path)
    setup.suites.script = [SuiteRun(results=(), timed_out=True)]
    with caplog.at_level(logging.ERROR):
        assert_harness_error(run(setup), caplog, "timed out")


def test_an_unresolvable_environment_is_a_rejection_with_the_reason(tmp_path: Path) -> None:
    error = EnvironmentResolutionError(
        EnvironmentFailureReason.LOCK_STALE_OR_UNRESOLVABLE, "lock is stale"
    )
    setup = world(tmp_path, enter_error=error)
    result = run(setup)
    assert result.record.rejection is CandidateRejection.ENVIRONMENT_UNRESOLVED
    assert result.record.detail == "lock_stale_or_unresolvable: lock is stale"
    assert result.record.environment is None
    assert setup.log == []


@pytest.mark.parametrize(
    "reason",
    [EnvironmentFailureReason.INSTALLER_MISSING, EnvironmentFailureReason.INSTALL_TIMEOUT],
)
def test_an_installer_failure_is_a_harness_error_not_a_rejection(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, reason: EnvironmentFailureReason
) -> None:
    setup = world(tmp_path, enter_error=EnvironmentResolutionError(reason, "uv: not found"))
    with caplog.at_level(logging.ERROR):
        result = run(setup)
    assert result.record.outcome is QualificationOutcome.HARNESS_ERROR
    assert result.record.rejection is None
    assert result.record.detail == f"{reason.value}: uv: not found"
    assert any(record.levelno == logging.ERROR for record in caplog.records)


@pytest.mark.parametrize("error", [SandboxError("git clone failed"), MissingHarnessHomeError()])
def test_a_sandbox_that_cannot_be_built_is_a_harness_error(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, error: Exception
) -> None:
    setup = world(tmp_path, enter_error=error)
    with caplog.at_level(logging.ERROR):
        result = run(setup)
    assert result.record.outcome is QualificationOutcome.HARNESS_ERROR
    assert result.record.environment is None
    assert any(record.levelno == logging.ERROR for record in caplog.records)
