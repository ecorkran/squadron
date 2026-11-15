"""Shared types of slice-case qualification (slice 426 D5, D6).

``SliceQualifyDeps`` is the one injected object the qualification stages take (DIP): tests
hand in fakes for the sandbox factory, the adapter, the suite runner, the stores and the clock.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from squadron.benchmark.adapter import SandboxContext
from squadron.benchmark.fairness import FixCaseAdapter
from squadron.benchmark.test_first import SuiteRunner
from squadron.core.process_runner import ProcessRunner
from squadron.metrology.benchmark_environment import EnvironmentIdentity
from squadron.metrology.benchmark_models import BenchmarkCase, TestRejection
from squadron.metrology.project_id import ProjectId
from squadron.metrology.slice_case_models import SliceCandidateRejection, SliceQualification


class SliceSandbox(Protocol):
    """What qualification uses of a built sandbox (``BenchmarkSandbox`` satisfies it)."""

    @property
    def identity(self) -> EnvironmentIdentity: ...

    def context(self) -> SandboxContext: ...

    def keep(self) -> None: ...


#: Builds a sandbox at a commit; entering installs the environment, leaving removes it
#: unless ``keep()`` was called.
SliceSandboxFactory = Callable[[str], AbstractContextManager[SliceSandbox]]


class QualificationStore(Protocol):
    """The qualification records qualification reads and writes."""

    def get_slice_qualification(
        self, project_id: ProjectId, slice_index: int, after_sha: str, env_digest: str | None
    ) -> SliceQualification | None: ...

    def write_slice_qualification(self, qualification: SliceQualification) -> str: ...

    def list_slice_qualifications(
        self, project_id: ProjectId | None = None
    ) -> list[SliceQualification]: ...


class CaseWriter(Protocol):
    def write_case(self, case: BenchmarkCase) -> str: ...


@dataclass(frozen=True)
class SliceQualifyDeps:
    project_id: ProjectId
    repo: Path
    runner: ProcessRunner
    qualifications: QualificationStore
    cases: CaseWriter
    sandbox_factory: SliceSandboxFactory
    adapter: FixCaseAdapter
    suite_runner: SuiteRunner
    repeats: int
    git_timeout_s: float
    clock: Callable[[], datetime]
    keep: bool = False


@dataclass(frozen=True)
class SliceQualifyResult:
    """The record a candidate ended with, whether it was reused, the case it produced and the
    sandbox trees left in place (``keep``)."""

    record: SliceQualification
    reused: bool = False
    case: BenchmarkCase | None = None
    kept_paths: tuple[Path, ...] = ()


@dataclass(frozen=True)
class StageOutcome:
    """What the sandbox stages decided, before it is stored as a ``SliceQualification``."""

    start_environment: EnvironmentIdentity
    reference_environment: EnvironmentIdentity
    excluded_with_reasons: tuple[tuple[str, TestRejection], ...]
    rejection: SliceCandidateRejection | None = None
    detail: str = ""
    case: BenchmarkCase | None = None
    kept_paths: tuple[Path, ...] = ()


@dataclass(frozen=True)
class ReusedRecord:
    """The sandbox stages found a stored result for this fork environment and ran nothing."""

    record: SliceQualification
    kept_paths: tuple[Path, ...] = ()
