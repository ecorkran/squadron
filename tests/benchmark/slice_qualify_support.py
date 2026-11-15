"""Doubles and builders for slice-case qualification tests (slice 426, Tasks 15-19).

Real git on the fixture repositories answers the pre-sandbox checks; the sandboxes, the
adapter and the suite runner are doubles, so no environment is installed and no test runs.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from squadron.benchmark.adapter import SandboxContext, SuiteRun, SuiteSelection
from squadron.benchmark.fairness import CollectedTests
from squadron.benchmark.scrubbed_env import CredentialGrant, ScrubbedEnvironment
from squadron.benchmark.slice_discovery import SliceCandidate
from squadron.benchmark.slice_qualify_types import SliceQualifyDeps, SliceSandbox
from squadron.core.process_runner import SubprocessRunner
from squadron.metrology.benchmark_environment import EnvironmentIdentity
from squadron.metrology.benchmark_models import BenchmarkCase, GraderCommand
from squadron.metrology.benchmark_nodes import NodeOutcome, NodeResult
from squadron.metrology.benchmark_store import BenchmarkRecordStore
from squadron.metrology.slice_case_store import SliceCaseRecordStore
from squadron.metrology.store import MetrologyStore
from tests.benchmark.slice_case_support import PROJECT, environment
from tests.benchmark.slice_repos import SliceRepo, landing_of

NOW = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)
FORK_ENV = environment("1" * 64)
TIP_ENV = environment("2" * 64)


def collected(digests: Mapping[str, str]) -> CollectedTests:
    return CollectedTests(digests=dict(digests), fixtures_reached={}, conftest_fixtures=())


class FakeSandbox:
    """A sandbox double: an environment identity, a tree path and a ``keep`` flag."""

    def __init__(self, tree: Path, identity: EnvironmentIdentity) -> None:
        self.tree = tree
        self.identity = identity
        self.kept = False

    def context(self) -> SandboxContext:
        return SandboxContext(
            tree=self.tree,
            output_dir=self.tree.with_suffix(".out"),
            env=ScrubbedEnvironment(self.tree.parent, "stub", CredentialGrant.none(), {}),
            runner=SubprocessRunner(),
            install_timeout_s=1,
            suite_timeout_s=1,
        )

    def keep(self) -> None:
        self.kept = True


@dataclass
class FakeFactory:
    """Builds ``FakeSandbox`` doubles by sha: the fork gets ``FORK_ENV``, the tip ``TIP_ENV``."""

    fork_sha: str
    tip_sha: str
    root: Path
    fork_env: EnvironmentIdentity = FORK_ENV
    fail: Callable[[str], Exception | None] = lambda sha: None
    built: list[str] = field(default_factory=lambda: [])
    sandboxes: dict[str, FakeSandbox] = field(default_factory=lambda: {})

    @contextmanager
    def __call__(self, sha: str) -> Iterator[SliceSandbox]:
        failure = self.fail(sha)
        if failure is not None:
            raise failure
        self.built.append(sha)
        identity = self.fork_env if sha == self.fork_sha else TIP_ENV
        sandbox = FakeSandbox(self.root / f"tree-{sha[:8]}", identity)
        self.sandboxes[sha] = sandbox
        yield sandbox


class FakeAdapter:
    """``collect`` answers by tree path; ``grader_commands`` is fixed."""

    def __init__(self, by_tree: Mapping[Path, CollectedTests]) -> None:
        self._by_tree = by_tree
        self.collected: list[Path] = []

    def collect(self, ctx: SandboxContext) -> CollectedTests:
        self.collected.append(ctx.tree)
        return self._by_tree[ctx.tree]

    def grader_commands(self, tree: Path) -> tuple[GraderCommand, ...]:
        return ()


class FakeSuite:
    """Each run answers from a script of ``{node id: outcome}`` maps; the last repeats.

    ``timed_out`` makes every run report a timeout; ``error`` makes every run raise it.
    """

    def __init__(
        self,
        runs: Sequence[Mapping[str, NodeOutcome]],
        *,
        timed_out: bool = False,
        error: Exception | None = None,
    ) -> None:
        self._runs = runs
        self._timed_out = timed_out
        self._error = error
        self.calls = 0

    def run_suite(self, ctx: SandboxContext, selection: SuiteSelection) -> SuiteRun:
        script = self._runs[min(self.calls, len(self._runs) - 1)]
        self.calls += 1
        if self._error is not None:
            raise self._error
        if self._timed_out:
            return SuiteRun(results=(), timed_out=True)
        return SuiteRun(
            results=tuple(NodeResult(node_id=node, outcome=out) for node, out in script.items())
        )


@dataclass
class Setup:
    deps: SliceQualifyDeps
    candidate: SliceCandidate
    factory: FakeFactory
    adapter: FakeAdapter
    suite: FakeSuite
    qualifications: SliceCaseRecordStore
    cases: BenchmarkRecordStore


def make_setup(
    tmp_path: Path,
    built: SliceRepo,
    *,
    fork_tests: Mapping[str, str],
    tip_tests: Mapping[str, str],
    suite_runs: Sequence[Mapping[str, NodeOutcome]],
    repeats: int = 3,
    keep: bool = False,
    runner: object | None = None,
    suite: FakeSuite | None = None,
    fail: Callable[[str], Exception | None] | None = None,
) -> Setup:
    metrology = MetrologyStore(store_dir=tmp_path / "store")
    cases = BenchmarkRecordStore(metrology)
    qualifications = SliceCaseRecordStore(cases)
    landing = built.landing
    factory = FakeFactory(landing.fork, landing.tip, tmp_path / "sandboxes")
    if fail is not None:
        factory.fail = fail
    adapter = FakeAdapter(
        {
            factory.root / f"tree-{landing.fork[:8]}": collected(fork_tests),
            factory.root / f"tree-{landing.tip[:8]}": collected(tip_tests),
        }
    )
    suite = suite or FakeSuite(suite_runs)
    deps = SliceQualifyDeps(
        project_id=PROJECT,
        repo=built.repo,
        runner=runner or SubprocessRunner(),  # type: ignore[arg-type]
        qualifications=qualifications,
        cases=cases,
        sandbox_factory=factory,
        adapter=adapter,
        suite_runner=suite,
        repeats=repeats,
        git_timeout_s=30.0,
        clock=lambda: NOW,
        keep=keep,
    )
    candidate = SliceCandidate(PROJECT, built.index, landing_of(built))
    return Setup(deps, candidate, factory, adapter, suite, qualifications, cases)


def case_of(setup: Setup, case_id: str) -> BenchmarkCase | None:
    return setup.cases.get_case(case_id)


#: Fork tests: u1 and u4 pass at the tip, u2 is flaky there, u3 always fails there, s1 is
#: removed by the slice and s2 is changed by it. The tip adds n1, the slice's own test.
FORK_TESTS = {"t::u1": "d", "t::u2": "d", "t::u3": "d", "t::u4": "d", "t::s1": "d", "t::s2": "old"}
TIP_TESTS = {
    "t::u1": "d",
    "t::u2": "d",
    "t::u3": "d",
    "t::u4": "d",
    "t::s2": "new",
    "t::n1": "d",
}
PASSING = NodeOutcome.PASSED
FAILING = NodeOutcome.FAILED
SUITE_RUNS = (
    {"t::u1": PASSING, "t::u2": PASSING, "t::u3": FAILING, "t::u4": PASSING, "t::n1": PASSING},
    {"t::u1": PASSING, "t::u2": FAILING, "t::u3": FAILING, "t::u4": PASSING, "t::n1": PASSING},
    {"t::u1": PASSING, "t::u2": PASSING, "t::u3": FAILING, "t::u4": PASSING, "t::n1": PASSING},
)


def typical_setup(tmp_path: Path, built: SliceRepo, **overrides: object) -> Setup:
    """A slice whose qualification ends with a case: two regression nodes, one flaky, one
    always failing, two superseded."""
    arguments: dict[str, object] = {
        "fork_tests": FORK_TESTS,
        "tip_tests": TIP_TESTS,
        "suite_runs": SUITE_RUNS,
    } | overrides
    return make_setup(tmp_path, built, **arguments)  # type: ignore[arg-type]
