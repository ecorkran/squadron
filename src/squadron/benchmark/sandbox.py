"""The benchmark sandbox: a history-free tree, a scrubbed home and an installed environment.

Composes ``HistoryFreeSandbox`` (tree ``<root>/<id>/``, lock ``<id>.lock``), a
``ScrubbedEnvironment`` (home ``<id>.home``) and an output directory ``<id>.out``. Entering
builds the tree, prepares the home, then resolves the language environment; every failed
enter and every exit removes all of them unless ``keep()`` was called (slice 421 D4, D7).
"""

from __future__ import annotations

import shutil
import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Self

from squadron.benchmark.adapter import (
    BenchmarkAdapter,
    EnvironmentIdentity,
    SandboxContext,
    SuiteRun,
    SuiteSelection,
)
from squadron.benchmark.scrubbed_env import CredentialGrant, ScrubbedEnvironment
from squadron.core.process_runner import ProcessRunner
from squadron.providers.base import ProfileName
from squadron.replay.history_free_sandbox import HistoryFreeSandbox
from squadron.replay.sandbox import sweep_orphans

HOME_SUFFIX = ".home"
OUT_SUFFIX = ".out"
SIBLING_SUFFIXES = (HOME_SUFFIX, OUT_SUFFIX)
#: ``sq benchmark recall``'s working directories under the benchmark root. The recall lock
#: guards them, not a lock of their own, so the orphan sweep must never remove them.
RECALL_SANDBOXES = "recall-sandboxes"
RECALL_OUT = "recall-out"
RECALL_HOMES = "recall-homes"
RECALL_DIRS = (RECALL_SANDBOXES, RECALL_OUT, RECALL_HOMES)


def benchmark_root() -> Path:
    """``~/.config/squadron/benchmark/`` — sibling of the ``replays`` root."""
    return Path.home() / ".config" / "squadron" / "benchmark"


def sweep_benchmark_orphans(runner: ProcessRunner, root: Path | None = None) -> None:
    """Remove benchmark sandboxes (tree, home, out, lock) whose owner process is gone."""
    sweep_orphans(
        runner,
        root if root is not None else benchmark_root(),
        sweep_cf_projects=False,
        sibling_suffixes=SIBLING_SUFFIXES,
        guarded_elsewhere=RECALL_DIRS,
    )


class BenchmarkSandbox:
    """Context manager owning one sandbox's four paths."""

    def __init__(
        self,
        *,
        start_sha: str,
        sandbox_id: str,
        repo_root: Path,
        runner: ProcessRunner,
        adapter: BenchmarkAdapter,
        harness_env: Mapping[str, str],
        install_timeout_s: float,
        suite_timeout_s: float,
        root: Path | None = None,
    ) -> None:
        self._root = root if root is not None else benchmark_root()
        self._sandbox_id = sandbox_id
        self._harness_env = harness_env
        self._runner = runner
        self._adapter = adapter
        self._install_timeout_s = install_timeout_s
        self._suite_timeout_s = suite_timeout_s
        self._history = HistoryFreeSandbox(
            start_sha=start_sha,
            sandbox_id=sandbox_id,
            repo_root=repo_root,
            runner=runner,
            root=self._root,
        )
        self._environment = ScrubbedEnvironment(
            self._root, sandbox_id, CredentialGrant.none(), harness_env
        )
        self._output_dir = self._root / f"{sandbox_id}{OUT_SUFFIX}"
        self._identity: EnvironmentIdentity | None = None
        self._kept = False

    @property
    def tree(self) -> Path:
        return self._history.path

    @property
    def home(self) -> Path:
        return self._environment.home

    @property
    def output_dir(self) -> Path:
        return self._output_dir

    @property
    def identity(self) -> EnvironmentIdentity:
        if self._identity is None:
            raise RuntimeError("the sandbox has not been entered")
        return self._identity

    def checkout_branch(self, name: str) -> None:
        """Put the tree on a new branch at the start commit.

        The tree starts detached, and a producer that commits (the ``fix`` pipeline) refuses a
        detached HEAD. The branch holds only the start commit, so the tree stays history-free.
        Raises ``SandboxError`` carrying git's stderr.
        """
        self._history.checked("git", "-C", str(self.tree), "checkout", "-q", "-b", name)

    def keep(self) -> None:
        """Leave all four paths in place on exit."""
        self._kept = True
        self._history.keep()

    def __enter__(self) -> Self:
        self._history.__enter__()
        built = False
        try:
            self._environment.prepare()
            self._output_dir.mkdir()
            self._identity = self._adapter.resolve_environment(self._context())
            built = True
        finally:
            if not built:
                self._cleanup()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if not self._kept:
            self._cleanup()

    def context(self) -> SandboxContext:
        """The context adapters take: tree, output directory, scrubbed environment, runner."""
        return self._context()

    def run_suite(self, selection: SuiteSelection) -> SuiteRun:
        """Run the project's tests under the scrubbed environment."""
        return self._adapter.run_suite(self._context(), selection)

    def reinstall(self) -> None:
        """Install again from the tree's current lock (the grader's reinstall, slice 425 D5).

        ``identity`` keeps naming the start environment, as the grader identity requires, and
        the grade records only that a reinstall happened. A failure raises
        ``EnvironmentResolutionError``.
        """
        self._adapter.resolve_environment(self._context())

    def process_env(self) -> dict[str, str]:
        """The environment for any child process in this sandbox."""
        return self._environment.variables(self._adapter.path_entries(self._context()))

    def producer_env(self, profile: ProfileName, tools: Sequence[str] = ()) -> dict[str, str]:
        """The environment for a producer child: ``process_env`` plus *profile*'s credentials.

        The producer's run state and transcripts are read from this same home, so its login
        must live in it. The grant is linked into the existing home (nothing already built is
        redone); ``process_env`` stays credential-free for suite runs. ``tools`` are extra
        executables the producer needs (a slice case's ``cf`` and ``node``, slice 426 D9),
        linked into the home the same way; a suite run never gets them.
        """
        environment = ScrubbedEnvironment(
            self._root,
            self._sandbox_id,
            CredentialGrant.for_profiles([profile]),
            self._harness_env,
        ).with_tools(tools)
        environment.grant_carryover_into_home()
        environment.link_extra_tools_into_home()
        return environment.variables(self._adapter.path_entries(self._context()))

    def _context(self) -> SandboxContext:
        return SandboxContext(
            tree=self.tree,
            output_dir=self._output_dir,
            env=self._environment,
            runner=self._runner,
            install_timeout_s=self._install_timeout_s,
            suite_timeout_s=self._suite_timeout_s,
        )

    def _cleanup(self) -> None:
        """Remove out, home, tree and lock. Never raises."""
        shutil.rmtree(self._output_dir, ignore_errors=True)
        self._environment.cleanup()
        self._history.cleanup()


def generate_sandbox_id(now: datetime | None = None) -> str:
    """A unique ``sandbox-{YYYYMMDD}-{uuid8}`` id."""
    stamp = (now or datetime.now(UTC)).strftime("%Y%m%d")
    return f"sandbox-{stamp}-{uuid.uuid4().hex[:8]}"
