"""The services ``sq benchmark grade`` and ``report`` are given: the commands' one seam.

``build_production_grade_services`` fills this with the real collaborators (a sandbox per
grade, real git and uv, the grading reviewer, the snapshot tools); command tests substitute
doubles, so no test runs a model, a sandbox or git. Nothing here chooses what to grade.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from squadron.benchmark.adapter import SandboxContext
from squadron.benchmark.bench_runner import OrphanSweep
from squadron.benchmark.grade_budget import ReviewBudget
from squadron.benchmark.grade_deps import GradeDeps, GradeSandbox
from squadron.benchmark.grade_one import grade_one
from squadron.benchmark.grade_plan import GradePlan
from squadron.benchmark.grade_review import resolve_reviewer, review_tree_diff
from squadron.benchmark.grade_runner import GradeFunction
from squadron.benchmark.grade_snapshot import make_snapshot_measurer
from squadron.benchmark.production_deps import CASE_LANGUAGE
from squadron.benchmark.registry import adapter_for, fix_case_adapter_for, grading_adapter_for
from squadron.benchmark.run_services import KeptSandbox
from squadron.benchmark.sandbox import (
    BenchmarkSandbox,
    benchmark_root,
    generate_sandbox_id,
    sweep_benchmark_orphans,
)
from squadron.benchmark.tree_reader import GitTreeReader
from squadron.codehost.git_refs import GIT_QUERY_TIMEOUT_SECONDS
from squadron.config.keys import BENCHMARK_INSTALL_TIMEOUT_KEY, BENCHMARK_SUITE_TIMEOUT_KEY
from squadron.config.manager import get_config, get_positive_int_config
from squadron.core.process_runner import ProcessRunner, SubprocessRunner
from squadron.metrology.benchmark_models import BenchmarkCase
from squadron.metrology.benchmark_store import BenchmarkRecordStore
from squadron.metrology.grade_models import ReviewerRef
from squadron.metrology.grade_store import GradeRecordStore
from squadron.metrology.identity import derive_project_id
from squadron.metrology.snapshot.registry import default_registry
from squadron.metrology.snapshot.runner import SubprocessToolRunner
from squadron.metrology.store import MetrologyStore, resolve_store_dir

#: ``(budget, plan, repositories, keep)`` -> the deps of one grade invocation.
DepsFactory = Callable[[ReviewBudget, GradePlan, Sequence[Path], bool], GradeDeps]


@dataclass(frozen=True)
class GradeServices:
    repo_root: Path
    store: BenchmarkRecordStore
    grade_store: GradeRecordStore
    process_runner: ProcessRunner
    #: Where the grade lock lives.
    lock_root: Path
    sweep: OrphanSweep
    clock: Callable[[], datetime]
    #: A config value by key, ``None`` when unset.
    read_config: Callable[[str], object | None]
    resolve_reviewer: Callable[[str], ReviewerRef]
    #: The project id of a repository, to match each case to a ``--repo``.
    project_id_of: Callable[[Path], str]
    make_deps: DepsFactory
    grade: GradeFunction
    #: The sandboxes this invocation created that are still on disk.
    kept_sandboxes: Callable[[], Sequence[KeptSandbox]]


class _Sandboxes:
    """Builds a sandbox at a case's start commit in the case's repository, and remembers it."""

    def __init__(self, runner: ProcessRunner, install_timeout_s: int, suite_timeout_s: int) -> None:
        self._runner = runner
        self._install_timeout_s = install_timeout_s
        self._suite_timeout_s = suite_timeout_s
        self.created: list[BenchmarkSandbox] = []

    def at(self, case: BenchmarkCase, repo_root: Path) -> BenchmarkSandbox:
        sandbox = BenchmarkSandbox(
            start_sha=case.start_sha,
            sandbox_id=generate_sandbox_id(),
            repo_root=repo_root,
            runner=self._runner,
            adapter=adapter_for(CASE_LANGUAGE),
            harness_env=dict(os.environ),
            install_timeout_s=self._install_timeout_s,
            suite_timeout_s=self._suite_timeout_s,
        )
        self.created.append(sandbox)
        return sandbox

    def kept(self) -> list[KeptSandbox]:
        return [
            KeptSandbox(tree=s.tree, home=s.home, output_dir=s.output_dir)
            for s in self.created
            if s.tree.exists()
        ]


def _collect_node_ids(sandbox: GradeSandbox, case: BenchmarkCase) -> tuple[str, ...]:
    context: SandboxContext = sandbox.context()
    return tuple(fix_case_adapter_for(CASE_LANGUAGE).collect(context).digests)


def build_production_grade_services(repo_root: Path) -> GradeServices:
    """The real collaborators for grading in *repo_root* (the store and config come from it)."""
    runner = SubprocessRunner()
    store = BenchmarkRecordStore(MetrologyStore(store_dir=resolve_store_dir(cwd=str(repo_root))))
    sandboxes = _Sandboxes(
        runner,
        get_positive_int_config(BENCHMARK_INSTALL_TIMEOUT_KEY, cwd=str(repo_root)),
        get_positive_int_config(BENCHMARK_SUITE_TIMEOUT_KEY, cwd=str(repo_root)),
    )

    def make_deps(
        budget: ReviewBudget, plan: GradePlan, repos: Sequence[Path], keep: bool
    ) -> GradeDeps:
        by_project = {derive_project_id(str(path)).value: path for path in repos}

        def repo_for(case: BenchmarkCase) -> Path:
            return by_project[case.project_id.value]

        return GradeDeps(
            grader=plan.grader,
            keep=keep,
            git_timeout_s=GIT_QUERY_TIMEOUT_SECONDS,
            sandbox_factory=lambda case: sandboxes.at(case, repo_for(case)),
            grading_adapter_for=lambda case: grading_adapter_for(CASE_LANGUAGE),
            reviewer=lambda tree, base: review_tree_diff(
                tree, base, plan.grader.reviewer, timeout_s=plan.review_timeout_s
            ),
            budget=budget,
            collect_node_ids=_collect_node_ids,
            measure_snapshot=make_snapshot_measurer(default_registry(), SubprocessToolRunner()),
            store=GradeRecordStore(store),
            repo_root_for=repo_for,
            tree_reader_for=lambda case, sha: GitTreeReader(runner, repo_for(case), sha),
            process_runner=runner,
            clock=lambda: datetime.now(UTC),
        )

    return GradeServices(
        repo_root=repo_root,
        store=store,
        grade_store=GradeRecordStore(store),
        process_runner=runner,
        lock_root=benchmark_root(),
        sweep=sweep_benchmark_orphans,
        clock=lambda: datetime.now(UTC),
        read_config=lambda key: get_config(key, cwd=str(repo_root)),
        resolve_reviewer=resolve_reviewer,
        project_id_of=lambda path: derive_project_id(str(path)).value,
        make_deps=make_deps,
        grade=grade_one,
        kept_sandboxes=sandboxes.kept,
    )
