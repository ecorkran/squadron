"""Orchestrate discovery, qualification and case-set writing for one repository (slice 422 D9, D13).

Every closing commit ends as exactly one stored ``FixQualification``: discovery rejections are
stored here, every candidate by ``qualify_candidate``. The qualified case ids become a case
set. ``BuildHalted`` from any stage propagates: the build stops with its reason.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from squadron.benchmark.build_errors import BuildHalted, halt
from squadron.benchmark.fix_discovery import DiscoveryResult, FixCandidate, discover
from squadron.benchmark.qualify import qualify_candidate
from squadron.benchmark.qualify_types import (
    QualifyDeps,
    QualifyResult,
    SandboxFactory,
    SandboxStages,
    record_discovery_rejection,
)
from squadron.benchmark.registry import adapter_for, fix_case_adapter_for
from squadron.codehost.protocol import CodeHost
from squadron.core.process_runner import ProcessRunner
from squadron.metrology.benchmark_models import CaseSet, FixQualification, QualificationOutcome
from squadron.metrology.benchmark_store import BenchmarkRecordStore
from squadron.metrology.errors import MetrologyIdentityError, MetrologyStoreError
from squadron.metrology.project_id import ProjectId
from squadron.metrology.snapshot_models import SourceLanguage

_logger = logging.getLogger(__name__)

SHA_DISPLAY_DIGITS = 8


@dataclass(frozen=True)
class BuildDeps:
    """Everything a build is given; ``build_fix_cases`` adds the project id and the adapters."""

    host: CodeHost
    store: BenchmarkRecordStore
    runner: ProcessRunner
    sandbox_stages: SandboxStages
    sandbox_factory: SandboxFactory
    derive_project_id: Callable[[str], ProjectId]
    repeats: int
    git_timeout_seconds: float


@dataclass(frozen=True)
class BuildResult:
    project_id: ProjectId
    records: tuple[FixQualification, ...]
    #: ``None`` when nothing qualified: no case set is written then.
    case_set: CaseSet | None

    @property
    def qualified_case_ids(self) -> tuple[str, ...]:
        return tuple(r.case_id for r in self.records if r.case_id is not None)


def _selected(
    discovered: DiscoveryResult, prefixes: Sequence[str]
) -> tuple[list[FixCandidate], list[str]]:
    """Candidates and discovery-rejected shas matching ``prefixes`` (all when none are given)."""
    if not prefixes:
        return list(discovered.candidates), [r.sha for r in discovered.rejections]
    known = [c.sha for c in discovered.candidates] + [r.sha for r in discovered.rejections]
    unknown = [prefix for prefix in prefixes if not any(sha.startswith(prefix) for sha in known)]
    if unknown:
        raise halt(f"no closing commit matches: {', '.join(unknown)}")

    def wanted(sha: str) -> bool:
        return any(sha.startswith(prefix) for prefix in prefixes)

    return (
        [c for c in discovered.candidates if wanted(c.sha)],
        [r.sha for r in discovered.rejections if wanted(r.sha)],
    )


def describe(result: QualifyResult) -> str:
    """The one line a candidate prints: its outcome, ``reused`` first when it was reused."""
    record = result.record
    if record.outcome is QualificationOutcome.QUALIFIED:
        hidden = sum(1 for verdict in record.hidden_verdicts if verdict.rejection is None)
        summary = f"qualified {record.case_id} ({hidden} hidden)"
    elif record.outcome is QualificationOutcome.HARNESS_ERROR:
        summary = f"harness_error: {record.detail}"
    else:
        summary = f"rejected {record.rejection.value if record.rejection else '?'}"
    return f"reused ({summary})" if result.reused else summary


def _derive_project(repo_root: Path, deps: BuildDeps) -> ProjectId:
    try:
        return deps.derive_project_id(str(repo_root))
    except MetrologyIdentityError as exc:
        raise halt(f"cannot identify the project in {repo_root}: {exc}") from exc


def _write_case_set(deps: BuildDeps, set_name: str, case_ids: Sequence[str]) -> CaseSet:
    try:
        return deps.store.write_case_set(set_name, tuple(case_ids))
    except MetrologyStoreError as exc:
        message = f"could not write case set '{set_name}': {exc}"
        _logger.exception(message)
        raise BuildHalted(message) from exc


def build_fix_cases(
    repo_root: Path,
    set_name: str,
    commits: Sequence[str],
    deps: BuildDeps,
    on_candidate: Callable[[str], None],
) -> BuildResult:
    """Qualify every closing commit in ``repo_root`` (or those matching ``commits``)."""
    project_id = _derive_project(repo_root, deps)
    qualify_deps = QualifyDeps(
        repo_root=repo_root,
        project_id=project_id,
        host=deps.host,
        store=deps.store,
        runner=deps.runner,
        adapter=fix_case_adapter_for(SourceLanguage.PYTHON),
        sandbox_stages=deps.sandbox_stages,
        sandbox_factory=deps.sandbox_factory,
        suite_runner=adapter_for(SourceLanguage.PYTHON),
        repeats=deps.repeats,
        git_timeout_seconds=deps.git_timeout_seconds,
    )
    discovered = discover(deps.runner, repo_root, timeout_seconds=deps.git_timeout_seconds)
    candidates, rejected_shas = _selected(discovered, commits)
    records: list[FixQualification] = []
    for rejection in discovered.rejections:
        if rejection.sha in rejected_shas:
            result = record_discovery_rejection(qualify_deps, rejection)
            records.append(result.record)
            on_candidate(f"{rejection.sha[:SHA_DISPLAY_DIGITS]} {describe(result)}")
    for candidate in candidates:
        result = qualify_candidate(candidate, qualify_deps)
        records.append(result.record)
        on_candidate(f"{candidate.sha[:SHA_DISPLAY_DIGITS]} {describe(result)}")
    case_ids = [r.case_id for r in records if r.case_id is not None]
    case_set = _write_case_set(deps, set_name, case_ids) if case_ids else None
    return BuildResult(project_id, tuple(records), case_set)
