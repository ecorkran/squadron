"""The benchmark sandbox: a history-free tree, a scrubbed home and an installed environment.

Composes ``HistoryFreeSandbox`` (tree ``<root>/<id>/``, lock ``<id>.lock``), a
``ScrubbedEnvironment`` (home ``<id>.home``) and an output directory ``<id>.out``. Entering
builds the tree, prepares the home, then resolves the language environment; every failed
enter and every exit removes all of them unless ``keep()`` was called (slice 421 D4, D7).
"""

from __future__ import annotations

import shutil
import uuid
from collections.abc import Mapping
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
from squadron.replay.history_free_sandbox import HistoryFreeSandbox
from squadron.replay.sandbox import sweep_orphans

HOME_SUFFIX = ".home"
OUT_SUFFIX = ".out"
SIBLING_SUFFIXES = (HOME_SUFFIX, OUT_SUFFIX)


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

    def run_suite(self, selection: SuiteSelection) -> SuiteRun:
        """Run the project's tests under the scrubbed environment."""
        return self._adapter.run_suite(self._context(), selection)

    def process_env(self) -> dict[str, str]:
        """The environment for any child process in this sandbox."""
        return self._environment.variables(self._adapter.path_entries(self._context()))

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
