"""The real collaborators of ``sq benchmark run`` (slice 424 Task 32).

Everything a replay needs that is not a decision of the command: the sandbox factory, 422's
qualification deps for re-qualifying a case, the leak-rule source and the installed ``sq``.
A missing input refuses naming it; nothing here has a default.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from squadron.benchmark.auth_check import (
    AuthAnswer,
    ProbeStartError,
    UnresolvedProfileError,
    run_auth_check,
)
from squadron.benchmark.bench_configs import aliases_without_cost, producer_config_ref
from squadron.benchmark.bench_plan import BenchmarkRefusal
from squadron.benchmark.bench_runner import ReplayFunction
from squadron.benchmark.case_runners import FixCaseRunner, case_runner_for, register_case_runner
from squadron.benchmark.fix_case_candidate import candidate_from_case
from squadron.benchmark.leak_rule_source import LeakRuleSource, installed_package_location, uv_cache_dir
from squadron.benchmark.qualify_sandbox import qualify_in_sandbox
from squadron.benchmark.qualify_types import QualifyDeps
from squadron.benchmark.registry import adapter_for, fix_case_adapter_for
from squadron.benchmark.replay_deps import ReplayOneDeps
from squadron.benchmark.replay_one import replay_one
from squadron.benchmark.run_services import KeptSandbox, ReplayContext, RunServices
from squadron.benchmark.sandbox import (
    BenchmarkSandbox,
    benchmark_root,
    generate_sandbox_id,
    sweep_benchmark_orphans,
)
from squadron.benchmark.scrubbed_env import MissingHarnessHomeError, MissingHarnessToolError
from squadron.benchmark.slice_runner_wiring import register_slice_runner
from squadron.benchmark.transcripts import transcript_source_for
from squadron.codehost.git_refs import GIT_QUERY_TIMEOUT_SECONDS
from squadron.codehost.github_cli import build_github_host
from squadron.codehost.protocol import CodeHost
from squadron.config.keys import (
    BENCHMARK_AUTH_PROBE_TIMEOUT_KEY,
    BENCHMARK_INSTALL_TIMEOUT_KEY,
    BENCHMARK_QUALIFICATION_REPEATS_KEY,
    BENCHMARK_SUITE_TIMEOUT_KEY,
)
from squadron.config.manager import get_config, get_positive_int_config
from squadron.core.process_runner import ProcessRunner, SubprocessRunner
from squadron.metrology.benchmark_models import CaseKind
from squadron.metrology.benchmark_store import BenchmarkRecordStore
from squadron.metrology.identity import derive_project_id
from squadron.metrology.snapshot_models import SourceLanguage
from squadron.metrology.store import MetrologyStore, resolve_store_dir
from squadron.pipeline.state import StateManager
from squadron.providers.base import ProfileName
from squadron.replay.runner import run_sq_subprocess

SQ_COMMAND = "sq"
#: Cases record no language yet, and Python is the only language with a benchmark adapter.
CASE_LANGUAGE = SourceLanguage.PYTHON


def resolve_sq_path() -> str:
    """The installed ``sq``, absolute: the scrubbed ``PATH`` cannot reach it."""
    found = shutil.which(SQ_COMMAND)
    if found is None:
        raise BenchmarkRefusal(f"{SQ_COMMAND} is not on PATH; the producer runs it by absolute path")
    return str(Path(found).resolve())


def _positive_int(key: str, repo_root: Path) -> int:
    try:
        return get_positive_int_config(key, cwd=str(repo_root))
    except ValueError as exc:
        raise BenchmarkRefusal(str(exc)) from exc


def _auth_check(
    aliases: Sequence[str], runner: ProcessRunner, sq_path: str, repo_root: Path
) -> dict[ProfileName, AuthAnswer]:
    timeout_s = _positive_int(BENCHMARK_AUTH_PROBE_TIMEOUT_KEY, repo_root)
    try:
        with TemporaryDirectory(prefix="sq-benchmark-auth-") as root:
            rows = run_auth_check(aliases, runner, Path(root), dict(os.environ), sq_path, timeout_s)
    except (
        UnresolvedProfileError,
        ProbeStartError,
        MissingHarnessToolError,
        MissingHarnessHomeError,
    ) as exc:
        raise BenchmarkRefusal(str(exc)) from exc
    return {row.profile: row.answer for row in rows}


class _Sandboxes:
    """Builds sandboxes at a commit and remembers them, so the run can say which survive."""

    def __init__(
        self, repo_root: Path, runner: ProcessRunner, install_timeout_s: int, suite_timeout_s: int
    ) -> None:
        self._repo_root, self._runner = repo_root, runner
        self._install_timeout_s, self._suite_timeout_s = install_timeout_s, suite_timeout_s
        self._created: list[BenchmarkSandbox] = []

    def at(self, start_sha: str) -> BenchmarkSandbox:
        sandbox = BenchmarkSandbox(
            start_sha=start_sha,
            sandbox_id=generate_sandbox_id(),
            repo_root=self._repo_root,
            runner=self._runner,
            adapter=adapter_for(CASE_LANGUAGE),
            harness_env=dict(os.environ),
            install_timeout_s=self._install_timeout_s,
            suite_timeout_s=self._suite_timeout_s,
        )
        self._created.append(sandbox)
        return sandbox

    def kept(self) -> list[KeptSandbox]:
        return [
            KeptSandbox(tree=s.tree, home=s.home, output_dir=s.output_dir)
            for s in self._created
            if s.tree.exists()
        ]


def _real_home() -> Path:
    home = os.environ.get("HOME")
    if not home:
        raise BenchmarkRefusal("HOME is not set; the leak scan needs the real home directory")
    return Path(home)


def _register_fix_runner(
    *,
    sq_path: str,
    repo_root: Path,
    runner: ProcessRunner,
    host: CodeHost,
    store: BenchmarkRecordStore,
    sandboxes: _Sandboxes,
) -> None:
    """Register the runner of fix cases, with 422's qualification deps for re-qualifying."""
    qualify_deps = QualifyDeps(
        repo_root=repo_root,
        project_id=derive_project_id(str(repo_root)),
        host=host,
        store=store,
        runner=runner,
        adapter=fix_case_adapter_for(CASE_LANGUAGE),
        sandbox_stages=qualify_in_sandbox,
        sandbox_factory=sandboxes.at,
        suite_runner=adapter_for(CASE_LANGUAGE),
        repeats=_positive_int(BENCHMARK_QUALIFICATION_REPEATS_KEY, repo_root),
        git_timeout_seconds=GIT_QUERY_TIMEOUT_SECONDS,
    )
    register_case_runner(
        CaseKind.FIX,
        FixCaseRunner(
            sq_path=sq_path,
            invoker=run_sq_subprocess,
            qualify_deps=qualify_deps,
            candidate_for=lambda case: candidate_from_case(
                case, runner, repo_root, GIT_QUERY_TIMEOUT_SECONDS
            ),
        ),
    )


def _replay_function_factory(
    *,
    runner: ProcessRunner,
    store: BenchmarkRecordStore,
    sandboxes: _Sandboxes,
    leak_rules: LeakRuleSource,
) -> Callable[[ReplayContext], ReplayFunction]:
    def replay_function(context: ReplayContext) -> ReplayFunction:
        deps = ReplayOneDeps(
            benchmark_id=context.benchmark_id,
            case_set=context.case_set,
            case_set_version=context.case_set_version,
            caps=context.caps,
            keep=context.keep,
            git_timeout_s=GIT_QUERY_TIMEOUT_SECONDS,
            sandbox_factory=lambda case: sandboxes.at(case.start_sha),
            runners=case_runner_for,
            store=store,
            state_reader_for=lambda runs_dir: StateManager(runs_dir=runs_dir),
            transcript_sources=transcript_source_for,
            leak_rules_for=leak_rules.rules_for,
            config_ref_for=lambda config: producer_config_ref(config.alias),
            process_runner=runner,
            clock=lambda: datetime.now(UTC),
        )
        return lambda case, config, sample: replay_one(case, config, sample, deps)

    return replay_function


def build_production_services(repo_root: Path) -> RunServices:
    """The real collaborators for a benchmark run in *repo_root*."""
    runner = SubprocessRunner()
    store = BenchmarkRecordStore(MetrologyStore(store_dir=resolve_store_dir(cwd=str(repo_root))))
    sq_path = resolve_sq_path()
    host = build_github_host(runner)
    sandboxes = _Sandboxes(
        repo_root,
        runner,
        _positive_int(BENCHMARK_INSTALL_TIMEOUT_KEY, repo_root),
        _positive_int(BENCHMARK_SUITE_TIMEOUT_KEY, repo_root),
    )
    leak_rules = LeakRuleSource(
        runner=runner,
        repo_root=repo_root,
        host=host,
        real_home=_real_home(),
        install_location=installed_package_location(),
        uv_cache=uv_cache_dir(runner),
        timeout_s=GIT_QUERY_TIMEOUT_SECONDS,
    )
    _register_fix_runner(
        sq_path=sq_path, repo_root=repo_root, runner=runner, host=host, store=store, sandboxes=sandboxes
    )
    register_slice_runner(
        sq_path=sq_path,
        repo_root=repo_root,
        runner=runner,
        store=store,
        sandbox_at=sandboxes.at,
        language=CASE_LANGUAGE,
        repeats=_positive_int(BENCHMARK_QUALIFICATION_REPEATS_KEY, repo_root),
        git_timeout_s=GIT_QUERY_TIMEOUT_SECONDS,
    )
    return RunServices(
        repo_root=repo_root,
        store=store,
        process_runner=runner,
        lock_root=benchmark_root(),
        sweep=sweep_benchmark_orphans,
        clock=lambda: datetime.now(UTC),
        runners=case_runner_for,
        transcript_sources=transcript_source_for,
        read_config=lambda key: get_config(key, cwd=str(repo_root)),
        auth_check=lambda aliases: _auth_check(aliases, runner, sq_path, repo_root),
        unpriced_aliases=aliases_without_cost,
        replay_function=_replay_function_factory(
            runner=runner, store=store, sandboxes=sandboxes, leak_rules=leak_rules
        ),
        kept_sandboxes=sandboxes.kept,
    )
