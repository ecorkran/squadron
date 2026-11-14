"""Where each replay's leak-scan facts come from (slice 424 Task 32).

``build_leak_rules`` takes every fact as a parameter; this module discovers them for a real
run: ``uv cache dir`` once, the installed package location, the case's ``[project].name`` at
its start commit, and its code-host owner and name. A missing fact refuses naming it.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import squadron
from squadron.benchmark.bench_plan import BenchmarkRefusal
from squadron.benchmark.build_errors import BuildHalted
from squadron.benchmark.case_runners import ReplaySandbox
from squadron.benchmark.fix_case_candidate import candidate_from_case
from squadron.benchmark.fix_discovery import DiscoveryRejection, resolve_locator
from squadron.benchmark.leak_rules import LeakRules, build_leak_rules
from squadron.codehost.protocol import CodeHost
from squadron.codehost.remotes import list_remotes
from squadron.core.process_runner import ProcessNotFoundError, ProcessRunner, ProcessTimedOutError
from squadron.metrology.benchmark_models import BenchmarkCase

PYPROJECT = "pyproject.toml"
UV_QUERY_TIMEOUT_S = 30


def uv_cache_dir(runner: ProcessRunner) -> Path:
    """The output of ``uv cache dir``; the leak scan treats that tree as outside the sandbox."""
    argv = ["uv", "cache", "dir"]
    try:
        result = runner.run(argv, cwd=None, timeout=UV_QUERY_TIMEOUT_S)
    except (ProcessNotFoundError, ProcessTimedOutError) as exc:
        raise BenchmarkRefusal(f"cannot read the uv cache location: {exc}") from exc
    if result.returncode != 0 or not result.stdout.strip():
        raise BenchmarkRefusal(f"`uv cache dir` exited {result.returncode}: {result.stderr.strip()}")
    return Path(result.stdout.strip())


def installed_package_location() -> Path:
    """The installed ``squadron`` package's own directory.

    Not its parent: that is ``site-packages``, which also holds every other library, and a
    producer reading one of those has not read the harness.
    """
    return Path(squadron.__file__).resolve().parent


def distribution_name(runner: ProcessRunner, repo_root: Path, sha: str, timeout_s: float) -> str:
    """``[project].name`` of the ``pyproject.toml`` at *sha*; refuses naming the file."""
    argv = ["git", "show", f"{sha}:{PYPROJECT}"]
    try:
        result = runner.run(argv, cwd=str(repo_root), timeout=timeout_s)
    except (ProcessNotFoundError, ProcessTimedOutError) as exc:
        raise BenchmarkRefusal(f"cannot read {PYPROJECT} at {sha[:12]}: {exc}") from exc
    if result.returncode != 0:
        raise BenchmarkRefusal(f"cannot read {PYPROJECT} at {sha[:12]}: {result.stderr.strip()}")
    try:
        name = tomllib.loads(result.stdout).get("project", {}).get("name")
    except tomllib.TOMLDecodeError as exc:
        raise BenchmarkRefusal(f"{PYPROJECT} at {sha[:12]} is not valid TOML: {exc}") from exc
    if not isinstance(name, str) or not name:
        raise BenchmarkRefusal(f"{PYPROJECT} at {sha[:12]} has no [project].name")
    return name


class LeakRuleSource:
    """Builds each replay's ``LeakRules``; per-case facts are read once and kept."""

    def __init__(
        self,
        *,
        runner: ProcessRunner,
        repo_root: Path,
        host: CodeHost,
        real_home: Path,
        install_location: Path,
        uv_cache: Path,
        timeout_s: float,
    ) -> None:
        self._runner, self._repo_root, self._host = runner, repo_root, host
        self._real_home, self._install, self._uv_cache = real_home, install_location, uv_cache
        self._timeout_s = timeout_s
        self._names: dict[str, str] = {}
        self._hosts: dict[str, tuple[str, str]] = {}

    def _owner_and_name(self, case: BenchmarkCase) -> tuple[str, str]:
        if case.case_id not in self._hosts:
            try:
                candidate = candidate_from_case(case, self._runner, self._repo_root, self._timeout_s)
            except BuildHalted as exc:
                raise BenchmarkRefusal(f"case {case.case_id}: {exc}") from exc
            remotes = list_remotes(self._runner, str(self._repo_root))
            located = resolve_locator(candidate, remotes, self._host)
            if isinstance(located, DiscoveryRejection):
                raise BenchmarkRefusal(
                    f"case {case.case_id}: no code host repository: {located.detail}"
                )
            self._hosts[case.case_id] = (located.owner, located.repository)
        return self._hosts[case.case_id]

    def _name(self, case: BenchmarkCase) -> str:
        if case.start_sha not in self._names:
            self._names[case.start_sha] = distribution_name(
                self._runner, self._repo_root, case.start_sha, self._timeout_s
            )
        return self._names[case.start_sha]

    def rules_for(self, sandbox: ReplaySandbox, case: BenchmarkCase) -> LeakRules:
        owner, repository = self._owner_and_name(case)
        return build_leak_rules(
            tree=sandbox.tree,
            home=sandbox.home,
            output_dir=sandbox.output_dir,
            real_home=self._real_home,
            repo_root=self._repo_root,
            install_location=self._install,
            uv_cache=self._uv_cache,
            distribution_name=self._name(case),
            host_owner=owner,
            host_repo=repository,
        )
