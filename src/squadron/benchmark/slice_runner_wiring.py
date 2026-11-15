"""Registers the slice-case runner on 424's case-kind seam with its real collaborators
(slice 426 D8). Called next to the fix runner's registration in ``production_deps``."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from squadron.benchmark.case_runners import register_case_runner
from squadron.benchmark.registry import adapter_for, fix_case_adapter_for
from squadron.benchmark.slice_qualify_types import SliceQualifyDeps, SliceSandboxFactory
from squadron.benchmark.slice_runner import SliceCaseRunner, candidate_from_case
from squadron.core.process_runner import ProcessRunner
from squadron.metrology.benchmark_models import CaseKind
from squadron.metrology.benchmark_store import BenchmarkRecordStore
from squadron.metrology.identity import derive_project_id
from squadron.metrology.slice_case_store import SliceCaseRecordStore
from squadron.metrology.snapshot_models import SourceLanguage
from squadron.replay.cf_registration import CfRegistration
from squadron.replay.runner import run_sq_subprocess


def register_slice_runner(
    *,
    sq_path: str,
    repo_root: Path,
    runner: ProcessRunner,
    store: BenchmarkRecordStore,
    sandbox_at: SliceSandboxFactory,
    language: SourceLanguage,
    repeats: int,
    git_timeout_s: float,
) -> SliceCaseRunner:
    """Build the slice-case runner and register it for ``CaseKind.SLICE``; returns it."""
    qualify_deps = SliceQualifyDeps(
        project_id=derive_project_id(str(repo_root)),
        repo=repo_root,
        runner=runner,
        qualifications=SliceCaseRecordStore(store),
        cases=store,
        sandbox_factory=sandbox_at,
        adapter=fix_case_adapter_for(language),
        suite_runner=adapter_for(language),
        repeats=repeats,
        git_timeout_s=git_timeout_s,
        clock=lambda: datetime.now(UTC),
    )
    slice_runner = SliceCaseRunner(
        sq_path=sq_path,
        invoker=run_sq_subprocess,
        runner=runner,
        registration_for=lambda env: CfRegistration(runner, env),
        qualify_deps=qualify_deps,
        candidate_for=lambda case: candidate_from_case(case, store.metrology_store),
    )
    register_case_runner(CaseKind.SLICE, slice_runner)
    return slice_runner
