"""What ``grade_one`` is handed, and how a grade ends without a result (slice 425 D1, D16).

Every collaborator is injected, so tests run no model and no git outside fixtures. A step
that cannot continue raises ``GradeAbsent`` after logging at ERROR; ``grade_one`` turns it
into a record carrying the absence and its class from ``GRADE_ABSENCE_CLASS``. Two failures
are not absences and propagate: ``GradeCapReached`` (the run stops, no record is written) and
``MissingReferenceGrade`` (a replay was planned before its reference was graded).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from squadron.benchmark.adapter import SandboxContext, SuiteRun, SuiteSelection
from squadron.benchmark.grade_budget import ReviewBudget
from squadron.benchmark.grading_adapter import GradingAdapter
from squadron.benchmark.tree_reader import TreeReader
from squadron.core.process_runner import ProcessRunner
from squadron.metrology.benchmark_environment import EnvironmentIdentity
from squadron.metrology.benchmark_models import BenchmarkCase
from squadron.metrology.content_sidecars import ContentSidecars
from squadron.metrology.diff_sidecars import DiffSidecars
from squadron.metrology.grade_models import (
    DETAIL_MAX_CHARS,
    GradeAbsence,
    GraderIdentity,
    GradeSubject,
    ReviewOutcome,
)
from squadron.metrology.grade_records import (
    ImplementationGrade,
    ReferenceGrade,
    SampleSizeEstimate,
)
from squadron.metrology.snapshot_models import CodeSnapshot

_logger = logging.getLogger(__name__)


class GradeAbsent(Exception):
    """A step ended the grade without a result; ``grade_one`` records the absence."""

    def __init__(self, absence: GradeAbsence, detail: str) -> None:
        super().__init__(f"{absence.value}: {detail}")
        self.absence = absence
        self.detail = _bounded(detail)


#: Marks a detail cut to fit the record; the tail is kept because tool errors end there.
_CUT_MARKER = "…"


def _bounded(detail: str) -> str:
    """*detail* within the record's cap; ``absent`` logs the full text at ERROR first."""
    if len(detail) <= DETAIL_MAX_CHARS:
        return detail
    return _CUT_MARKER + detail[-(DETAIL_MAX_CHARS - len(_CUT_MARKER)) :]


def absent(absence: GradeAbsence, detail: str) -> GradeAbsent:
    """Log *detail* at ERROR and return the ``GradeAbsent`` to raise."""
    _logger.error("grade absent (%s): %s", absence.value, detail)
    return GradeAbsent(absence, detail)


class MissingReferenceGrade(Exception):
    """A replay was graded before its case's reference was; the runner orders them (D8)."""

    def __init__(self, case_id: str, environment_digest: str) -> None:
        super().__init__(
            f"no usable reference grade for case {case_id} in environment {environment_digest[:8]}"
        )
        self.case_id = case_id
        self.environment_digest = environment_digest


@dataclass(frozen=True)
class GradeTarget:
    """What to grade: a case's reference, or one stored replay.

    ``environment_digest`` is the digest the grade sandbox must reproduce: the replay's own,
    or for a reference the one it was planned for (one reference per case and digest, D8).
    """

    subject: GradeSubject
    environment_digest: str
    replay_id: str | None = None
    benchmark_id: str | None = None
    #: The replay's stored diff (``diffs`` sidecar); ``None`` for a reference.
    diff_sha256: str | None = None


class GradeSandbox(Protocol):
    """What a grade uses of its sandbox; ``BenchmarkSandbox`` satisfies it."""

    @property
    def tree(self) -> Path: ...

    @property
    def identity(self) -> EnvironmentIdentity: ...

    def context(self) -> SandboxContext: ...

    def keep(self) -> None: ...

    def process_env(self) -> dict[str, str]: ...

    def reinstall(self) -> None: ...

    def run_suite(self, selection: SuiteSelection) -> SuiteRun: ...


class GradeStore(Protocol):
    """The record methods and sidecars one grade touches."""

    diffs: DiffSidecars
    snapshots: ContentSidecars
    nodes: ContentSidecars
    reviews: ContentSidecars

    def write_reference_grade(self, grade: ReferenceGrade) -> str: ...

    def write_grade(self, grade: ImplementationGrade) -> str: ...

    def get_reference_grade(
        self, case_id: str, grader_digest: str, environment_digest: str
    ) -> ReferenceGrade | None: ...

    def grades_for(self, benchmark_id: str) -> list[tuple[str, ImplementationGrade]]: ...

    def delete_grades(self, record_ids: Sequence[str]) -> int: ...

    def write_estimate(self, estimate: SampleSizeEstimate) -> str: ...


#: ``(tree, base_sha)`` -> the review of ``base_sha..HEAD``; raises ``ReviewFailed``.
Reviewer = Callable[[Path, str], ReviewOutcome]
#: ``(tree, case, head_sha)`` -> the snapshot of the tracked files of *tree* at *head_sha*,
#: measured under the tree's own snapshot config and writing no record (slice 425 D12).
SnapshotMeasurer = Callable[[Path, BenchmarkCase, str], CodeSnapshot]
#: ``(sandbox, case)`` -> the node ids pytest collects in the sandbox's tree now.
NodeCollector = Callable[["GradeSandbox", BenchmarkCase], tuple[str, ...]]


@dataclass(frozen=True)
class GradeDeps:
    grader: GraderIdentity
    #: ``--keep``: leave the sandbox in place after a written record.
    keep: bool
    git_timeout_s: float
    sandbox_factory: Callable[[BenchmarkCase], AbstractContextManager[GradeSandbox]]
    grading_adapter_for: Callable[[BenchmarkCase], GradingAdapter]
    reviewer: Reviewer
    budget: ReviewBudget
    collect_node_ids: NodeCollector
    measure_snapshot: SnapshotMeasurer
    store: GradeStore
    #: The user's checkout holding the case's project: where the reference commit lives.
    repo_root_for: Callable[[BenchmarkCase], Path]
    #: ``(case, sha)`` -> a reader of that commit's tree in the user's checkout.
    tree_reader_for: Callable[[BenchmarkCase, str], TreeReader]
    process_runner: ProcessRunner
    clock: Callable[[], datetime]
