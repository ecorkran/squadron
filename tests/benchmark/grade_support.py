"""Doubles and builders for the ``grade_one`` tests (slice 425 Tasks 24-31).

``make_world`` assembles ``GradeDeps`` over a real git clone of the grading fixture repo, a real
record store in a temp directory, and scripted doubles for the sandbox's suite runs, the review
and the snapshot, each of which also appends to one shared call log so tests can assert order.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Callable, Iterator, Sequence
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from squadron.benchmark.adapter import (
    EnvironmentResolutionError,
    NodeOutcome,
    NodeResult,
    SandboxContext,
    SuiteRun,
    SuiteSelection,
)
from squadron.benchmark.grade_budget import ReviewBudget
from squadron.benchmark.grade_deps import GradeDeps, GradeSandbox, GradeTarget
from squadron.benchmark.grade_run import GradeRun
from squadron.benchmark.grading_adapter import GradingAdapter, InjectionResult, RestorationResult
from squadron.benchmark.python_grading import PythonGradingAdapter
from squadron.benchmark.tree_reader import GitTreeReader, TreeReader
from squadron.core.process_runner import SubprocessRunner
from squadron.metrology.benchmark_environment import EnvironmentIdentity
from squadron.metrology.benchmark_models import BenchmarkCase
from squadron.metrology.benchmark_store import BenchmarkRecordStore
from squadron.metrology.grade_models import GradeSubject, ReviewOutcome, SuppressionCounts
from squadron.metrology.grade_records import ReferenceGrade
from squadron.metrology.grade_store import GradeRecordStore
from squadron.metrology.snapshot_models import CodeSnapshot, SnapshotMetric, SourceLanguage
from squadron.metrology.store import MetrologyStore
from tests.benchmark.grading_fixtures import GradingRepo, make_grading_case
from tests.benchmark.test_grade_identity import make_identity
from tests.metrology.snapshot.builders import make_measured_snapshot

ENVIRONMENT = EnvironmentIdentity(
    language=SourceLanguage.PYTHON,
    lockfile_path="uv.lock",
    lockfile_sha256="1" * 64,
    interpreter_version="3.12.1",
    installer_version="uv 0.13.5",
    platform="test",
    scrub_spec_version=1,
)
OTHER_ENVIRONMENT = ENVIRONMENT.model_copy(update={"interpreter_version": "3.13.0"})
REPLAY_ID = "implreplay-aaaaaaaaaaaa-bbbbbbbbbbbb-cccccccc-s1"
BENCHMARK_ID = "bench-1"
NOW = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)


def no_suite(selection: SuiteSelection) -> SuiteRun:
    raise AssertionError(f"run_suite was not expected, got {selection}")


def passing(selection: SuiteSelection) -> SuiteRun:
    ids = selection.node_ids or ()
    return SuiteRun(results=tuple(NodeResult(node_id=i, outcome=NodeOutcome.PASSED) for i in ids))


class FakeSandbox:
    """A directory-backed sandbox over a real git clone; suite runs come from a script."""

    def __init__(
        self,
        tree: Path,
        identity: EnvironmentIdentity,
        suites: Callable[[SuiteSelection], SuiteRun],
        log: list[str],
        reinstall_error: Exception | None = None,
    ) -> None:
        self.tree = tree
        self.identity = identity
        self.kept = False
        self._suites = suites
        self._log = log
        self._reinstall_error = reinstall_error

    def context(self) -> SandboxContext:
        raise AssertionError("the sandbox context was not expected")

    def keep(self) -> None:
        self.kept = True

    def process_env(self) -> dict[str, str]:
        return dict(os.environ)

    def reinstall(self) -> None:
        self._log.append("reinstall")
        if self._reinstall_error is not None:
            raise self._reinstall_error

    def run_suite(self, selection: SuiteSelection) -> SuiteRun:
        self._log.append(f"suite:{len(selection.node_ids or ())}")
        return self._suites(selection)


@dataclass
class SandboxFactory:
    """``deps.sandbox_factory``: clones the fixture repo at the case's start commit."""

    repo: GradingRepo
    base: Path
    identity: EnvironmentIdentity = ENVIRONMENT
    suites: Callable[[SuiteSelection], SuiteRun] = no_suite
    fail: Exception | None = None
    log: list[str] = field(default_factory=list[str])
    reinstall_error: Exception | None = None
    opened: list[FakeSandbox] = field(default_factory=list[FakeSandbox])
    removed: list[Path] = field(default_factory=list[Path])

    def __call__(self, case: BenchmarkCase) -> AbstractContextManager[GradeSandbox]:
        return self._open(case)

    @contextmanager
    def _open(self, case: BenchmarkCase) -> Iterator[GradeSandbox]:
        if self.fail is not None:
            raise self.fail
        tree = self.base / f"sandbox-{len(self.opened)}"
        subprocess.run(
            ["git", "clone", "-q", "--no-hardlinks", str(self.repo.root), str(tree)], check=True
        )
        subprocess.run(["git", "checkout", "-q", "--detach", case.start_sha], cwd=tree, check=True)
        sandbox = FakeSandbox(tree, self.identity, self.suites, self.log, self.reinstall_error)
        self.opened.append(sandbox)
        try:
            yield sandbox
        finally:
            if not sandbox.kept:
                shutil.rmtree(tree, ignore_errors=True)
                self.removed.append(tree)


@dataclass
class World:
    case: BenchmarkCase
    deps: GradeDeps
    store: GradeRecordStore
    factory: SandboxFactory
    repo: GradingRepo
    log: list[str]

    def run(self, target: GradeTarget, sandbox: GradeSandbox) -> GradeRun:
        """A ``GradeRun`` over an already opened sandbox, for tests of single steps."""
        return GradeRun(
            case=self.case,
            target=target,
            deps=self.deps,
            sandbox=sandbox,
            adapter=self.deps.grading_adapter_for(self.case),
            start=self.deps.tree_reader_for(self.case, self.case.start_sha),
            reference=self.deps.tree_reader_for(self.case, self.case.reference_sha),
        )

    def replay_target(self, diff: bytes, environment: EnvironmentIdentity = ENVIRONMENT) -> GradeTarget:
        ref = self.store.diffs.put(diff)
        return GradeTarget(
            subject=GradeSubject.REPLAY,
            environment_digest=environment.identity_digest,
            replay_id=REPLAY_ID,
            benchmark_id=BENCHMARK_ID,
            diff_sha256=ref.sha256,
        )

    def reference_target(self, environment: EnvironmentIdentity = ENVIRONMENT) -> GradeTarget:
        return GradeTarget(
            subject=GradeSubject.REFERENCE, environment_digest=environment.identity_digest
        )


def quiet_review(tree: Path, base: str) -> ReviewOutcome:
    """A review that finds nothing and costs a little."""
    return ReviewOutcome(findings=(), unnormalized_count=0, cost_usd=0.1, rules_hash=None)


def default_snapshot(tree: Path, case: BenchmarkCase, head_sha: str) -> CodeSnapshot:
    """A Python snapshot with lint total 4 and type total 2 (``make_measured_snapshot``)."""
    return make_measured_snapshot()


def no_collect(sandbox: GradeSandbox, case: BenchmarkCase) -> tuple[str, ...]:
    raise AssertionError("node collection was not expected")


def make_world(
    tmp_path: Path,
    grading_repo: GradingRepo,
    *,
    case: BenchmarkCase | None = None,
    reviewer: Callable[[Path, str], ReviewOutcome] | None = None,
    measure: Callable[[Path, BenchmarkCase, str], CodeSnapshot] = default_snapshot,
    collect: Callable[[GradeSandbox, BenchmarkCase], tuple[str, ...]] = no_collect,
    budget: ReviewBudget | None = None,
    keep: bool = False,
    identity: EnvironmentIdentity = ENVIRONMENT,
    suites: Callable[[SuiteSelection], SuiteRun] = no_suite,
    fail: Exception | None = None,
    reinstall_error: Exception | None = None,
    adapter: Callable[[], GradingAdapter] = PythonGradingAdapter,
) -> World:
    log: list[str] = []
    chosen_case = case or make_grading_case(grading_repo)
    factory = SandboxFactory(
        grading_repo, tmp_path / "sandboxes", identity, suites, fail, log, reinstall_error
    )
    (tmp_path / "sandboxes").mkdir(parents=True, exist_ok=True)
    store = GradeRecordStore(BenchmarkRecordStore(MetrologyStore(store_dir=tmp_path / "store")))

    def no_review(tree: Path, base: str) -> ReviewOutcome:
        raise AssertionError("the reviewer was not expected")

    runner = SubprocessRunner()
    deps = GradeDeps(
        grader=make_identity(),
        keep=keep,
        git_timeout_s=60,
        sandbox_factory=factory,
        grading_adapter_for=lambda _case: adapter(),
        reviewer=reviewer or no_review,
        budget=budget or ReviewBudget(cap_usd=100.0, per_review_usd=0.2),
        collect_node_ids=collect,
        measure_snapshot=measure,
        store=store,
        repo_root_for=lambda _case: grading_repo.root,
        tree_reader_for=lambda _case, sha: GitTreeReader(runner, grading_repo.root, sha),
        process_runner=runner,
        clock=lambda: NOW,
    )
    return World(chosen_case, deps, store, factory, grading_repo, log)


def failing_environment(reason_detail: str = "uv sync failed") -> EnvironmentResolutionError:
    from squadron.benchmark.adapter import EnvironmentFailureReason

    return EnvironmentResolutionError(
        EnvironmentFailureReason.LOCK_STALE_OR_UNRESOLVABLE, reason_detail
    )


def seed_reference(world: World, start_ids: Sequence[str]) -> ReferenceGrade:
    """Store a passing reference grade for the world's case, with *start_ids* as its baseline."""
    from tests.benchmark.test_grade_records import make_reference

    digest = world.store.nodes.put(json.dumps(list(start_ids)).encode("utf-8"))
    reference = make_reference(
        case_id=world.case.case_id,
        grader=world.deps.grader,
        environment_digest=ENVIRONMENT.identity_digest,
        baseline_nodes=digest,
    )
    world.store.write_reference_grade(reference)
    return reference


def edit_measurement(snapshot: CodeSnapshot, metric: SnapshotMetric, **updates: object) -> CodeSnapshot:
    """A copy of *snapshot* with *metric*'s Python measurement replaced by an updated copy."""
    python = snapshot.languages[0]
    measurements = [
        m.model_copy(update=updates) if m.metric is metric else m for m in python.measurements
    ]
    language = python.model_copy(update={"measurements": measurements})
    return snapshot.model_copy(update={"languages": [language]})


class LoggingAdapter:
    """The real Python adapter, recording the order its methods are called in."""

    def __init__(self, log: list[str]) -> None:
        self._inner = PythonGradingAdapter()
        self._log = log
        self.language = self._inner.language

    def restore_tool_config(self, tree: Path, start: TreeReader) -> RestorationResult:
        self._log.append("restore")
        return self._inner.restore_tool_config(tree, start)

    def deps_changed(self, tree: Path, start: TreeReader) -> bool:
        self._log.append("deps_changed")
        return self._inner.deps_changed(tree, start)

    def test_side_edits(self, tree: Path, start: TreeReader) -> tuple[str, ...]:
        return self._inner.test_side_edits(tree, start)

    def restore_test_files(self, tree: Path, start: TreeReader, paths: Sequence[str]) -> None:
        self._log.append("restore_tests")
        self._inner.restore_test_files(tree, start, paths)

    def inject_hidden(
        self, tree: Path, case: BenchmarkCase, start: TreeReader, reference: TreeReader
    ) -> InjectionResult:
        self._log.append("inject")
        return self._inner.inject_hidden(tree, case, start, reference)

    def count_suppressions(self, diff: bytes) -> SuppressionCounts:
        return self._inner.count_suppressions(diff)


class LoggingBudget(ReviewBudget):
    def __init__(self, log: list[str], cap_usd: float = 100.0, per_review_usd: float = 0.2) -> None:
        super().__init__(cap_usd, per_review_usd)
        self._log = log

    def before_review(self) -> None:
        self._log.append("budget_check")
        super().before_review()

    def after_review(self, cost_usd: float | None) -> None:
        self._log.append("budget_charge")
        super().after_review(cost_usd)


def passing_suite(
    seen: list[SuiteSelection] | None = None,
    outcomes: dict[str, NodeOutcome] | None = None,
) -> Callable[[SuiteSelection], SuiteRun]:
    """A suite double: every selected node passes unless *outcomes* says otherwise."""

    def suite(selection: SuiteSelection) -> SuiteRun:
        if seen is not None:
            seen.append(selection)
        mapping = outcomes or {}
        ids = selection.node_ids or ()
        return SuiteRun(
            results=tuple(
                NodeResult(node_id=i, outcome=mapping.get(i, NodeOutcome.PASSED)) for i in ids
            )
        )

    return suite


def replay_world(
    tmp_path: Path,
    repo: GradingRepo,
    variant: str = "producer_a",
    *,
    start_ids: Sequence[str] = ("t.py::a", "t.py::b"),
    case: BenchmarkCase | None = None,
    **kwargs: object,
) -> tuple[World, bytes]:
    """A world with a seeded reference, a quiet reviewer, and a replay diff from *variant*."""
    from tests.benchmark.grading_fixtures import build_variant

    ids = tuple(start_ids)
    options: dict[str, object] = {
        "reviewer": quiet_review,
        "suites": passing_suite(),
        "collect": lambda sandbox, c: ids,
    }
    options.update(kwargs)
    world = make_world(tmp_path, repo, case=case, **options)  # type: ignore[arg-type]
    seed_reference(world, ids)
    return world, build_variant(repo, variant, tmp_path / "producer").diff()
