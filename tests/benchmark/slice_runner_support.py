"""Doubles for the slice-case runner tests (slice 426, Tasks 24-25).

The sandbox double is a real git tree (so ``git branch --show-current`` is real) with a real
scrubbed home, so the environment the runner hands to cf and ``sq`` is the real one.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from squadron.benchmark.bench_plan import BenchConfig, Caps
from squadron.benchmark.scrubbed_env import CredentialGrant, ScrubbedEnvironment
from squadron.core.process_runner import ProcessResult, SubprocessRunner
from squadron.metrology.benchmark_environment import EnvironmentIdentity
from squadron.metrology.benchmark_models import BenchmarkCase, CaseKind, CaseProvenance
from squadron.providers.base import ProfileName
from squadron.replay.cf_registration import CfRegistration
from tests.benchmark.slice_case_support import PROJECT, environment
from tests.conftest import run_test_git

SLICE_INDEX = 403
AFTER_SHA = "b" * 40
CONFIG = BenchConfig(alias="opus", model="claude-x", profile="sdk", effort_configured=None)
CAPS = Caps(run_cap_usd=20.0, per_replay_cap_usd=8.0, per_replay_source="--max-cost-per-replay")
SQ_PATH = "/installed/bin/sq"
PLAN = "project-documents/user/architecture/500-slices.demo.md"
PLAN_TEXT = f"# Plan\n\n1. [ ] **({SLICE_INDEX}) Demo** — text. Effort: 2/5\n"


def slice_case(
    index: int = SLICE_INDEX, after_sha: str = AFTER_SHA, task: str = "## File: design\n"
) -> BenchmarkCase:
    return BenchmarkCase.build(
        project_id=PROJECT,
        kind=CaseKind.SLICE,
        start_sha="f" * 40,
        reference_sha="a" * 40,
        task_text=task,
        hidden_tests=(),
        hidden_fixtures=(),
        superseded_tests=(),
        excluded_tests=(),
        grader_commands=(),
        provenance=CaseProvenance(
            source_ref=f"slice:{index}@{after_sha}",
            created_at=datetime(2026, 11, 15, tzinfo=UTC),
            built_by="test",
        ),
    )


@dataclass
class Events:
    """A thread-safe log of what happened, in order."""

    items: list[str] = field(default_factory=lambda: [])
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def add(self, item: str) -> None:
        with self._lock:
            self.items.append(item)


@dataclass(frozen=True)
class CfCall:
    argv: tuple[str, ...]
    cwd: str | None
    env: Mapping[str, str] | None
    replace_env: bool


class CfRecorder:
    """A process runner that records every ``cf`` call and fails the ones it is told to."""

    def __init__(self, events: Events, fail_prefix: tuple[str, ...] | None = None) -> None:
        self.calls: list[CfCall] = []
        self._events = events
        self._fail_prefix = fail_prefix
        self._lock = threading.Lock()

    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: str | None,
        timeout: float,
        env: Mapping[str, str] | None = None,
        stdin: str | None = None,
        replace_env: bool = False,
    ) -> ProcessResult:
        call = tuple(argv)
        with self._lock:
            self.calls.append(CfCall(call, cwd, env, replace_env))
        self._events.add("cf " + " ".join(call[1:]))
        if self._fail_prefix and call[1 : 1 + len(self._fail_prefix)] == self._fail_prefix:
            return ProcessResult(argv=call, returncode=1, stdout="", stderr="cf exploded\n")
        return ProcessResult(argv=call, returncode=0, stdout="", stderr="")


class Invoker:
    """Records ``sq`` invocations."""

    def __init__(self, events: Events) -> None:
        self.calls: list[tuple[list[str], Path, Mapping[str, str] | None]] = []
        self._events = events
        self._lock = threading.Lock()

    def __call__(
        self, argv: Sequence[str], cwd: Path, env: Mapping[str, str] | None = None
    ) -> ProcessResult:
        with self._lock:
            self.calls.append((list(argv), cwd, env))
        self._events.add("sq run")
        return ProcessResult(argv=tuple(argv), returncode=0, stdout="", stderr="")


class SandboxDouble:
    """A git tree holding the slice plan, with a real scrubbed home beside it."""

    def __init__(
        self, root: Path, sandbox_id: str, tools_dir: Path, *, detached: bool, branch: str = "main"
    ) -> None:
        self.tree = root / sandbox_id
        self.output_dir = root / f"{sandbox_id}.out"
        self.identity: EnvironmentIdentity = environment()
        self.kept = False
        self.tool_requests: list[Sequence[str]] = []
        self.created_branches: list[str] = []
        (self.tree / PLAN).parent.mkdir(parents=True)
        (self.tree / PLAN).write_text(PLAN_TEXT)
        run_test_git(self.tree, "init", "-q", "-b", branch)
        run_test_git(self.tree, "add", "-A")
        run_test_git(self.tree, "commit", "-q", "-m", "start")
        if detached:
            run_test_git(self.tree, "checkout", "-q", "--detach")
        real_home = root / f"{sandbox_id}.realhome"
        real_home.mkdir()
        self._harness_env = {"HOME": str(real_home), "PATH": str(tools_dir)}
        self._environment = ScrubbedEnvironment(
            root, sandbox_id, CredentialGrant.none(), self._harness_env
        )
        self._environment.prepare()
        self.home = self._environment.home

    def producer_env(self, profile: ProfileName, tools: Sequence[str] = ()) -> dict[str, str]:
        self.tool_requests.append(tuple(tools))
        environment = ScrubbedEnvironment(
            self.home.parent,
            self.home.name.removesuffix(".home"),
            CredentialGrant.none(),
            self._harness_env,
        ).with_tools(tools)
        environment.link_extra_tools_into_home()
        return environment.variables(())

    def checkout_branch(self, name: str) -> None:
        self.created_branches.append(name)
        run_test_git(self.tree, "checkout", "-q", "-b", name)

    def keep(self) -> None:
        self.kept = True

    def branch(self) -> str:
        return run_test_git(self.tree, "branch", "--show-current").strip()


def make_tools_dir(root: Path) -> Path:
    """A fake harness ``PATH`` directory holding git, uv, cf and node stubs."""
    directory = root / "tools"
    directory.mkdir(parents=True, exist_ok=True)
    for name in ("git", "uv", "cf", "node"):
        tool = directory / name
        tool.write_text("#!/bin/sh\n")
        tool.chmod(0o755)
    return directory


def registration_factory(recorder: CfRecorder) -> Callable[[Mapping[str, str]], CfRegistration]:
    return lambda env: CfRegistration(recorder, env)


def real_git_runner() -> SubprocessRunner:
    return SubprocessRunner()
