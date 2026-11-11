"""The benchmark adapter seam: what a language supplies to run a case (slice 421 D6, D9, D11).

Separate from 400's ``LanguageAdapter`` (snapshot measurement): the clients differ, and
merging them would make every snapshot adapter stub execution methods. 422 adds fairness
rules and 425 hidden-test injection, each in its own slice.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol, Self

from squadron.benchmark.scrubbed_env import ScrubbedEnvironment
from squadron.core.process_runner import ProcessRunner
from squadron.metrology.benchmark_environment import EnvironmentIdentity
from squadron.metrology.snapshot_models import SourceLanguage


class EnvironmentFailureReason(StrEnum):
    NO_LOCKFILE = "no_lockfile"
    LOCKFILE_UNSUPPORTED = "lockfile_unsupported"
    LOCK_STALE_OR_UNRESOLVABLE = "lock_stale_or_unresolvable"
    INSTALL_TIMEOUT = "install_timeout"
    INSTALLER_MISSING = "installer_missing"


class FailureKind(StrEnum):
    COLLECTION_ERROR = "collection_error"
    MISSING_SYMBOL = "missing_symbol"
    ASSERTION_FAILURE = "assertion_failure"
    PROJECT_EXCEPTION = "project_exception"
    OTHER_EXCEPTION = "other_exception"


class NodeOutcome(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"
    XFAILED = "xfailed"
    XPASSED = "xpassed"
    NOT_RUN = "not_run"


class EnvironmentResolutionError(Exception):
    """The sandbox environment could not be installed; ``detail`` carries the tool's stderr."""

    def __init__(self, reason: EnvironmentFailureReason, detail: str) -> None:
        super().__init__(f"{reason.value}: {detail}")
        self.reason = reason
        self.detail = detail


class SuiteRunError(Exception):
    """The suite run produced no usable report; carries pytest's stderr."""


@dataclass(frozen=True)
class NodeResult:
    node_id: str
    outcome: NodeOutcome
    failure_kind: FailureKind | None = None
    phase: str | None = None
    exception_type: str | None = None


@dataclass(frozen=True)
class SuiteSelection:
    """All tests or specific node ids, either way minus ``deselect`` node ids."""

    node_ids: tuple[str, ...] | None
    deselect: tuple[str, ...] = ()

    @classmethod
    def all_tests(cls, deselect: tuple[str, ...] = ()) -> Self:
        return cls(node_ids=None, deselect=deselect)

    @classmethod
    def nodes(cls, ids: tuple[str, ...], deselect: tuple[str, ...] = ()) -> Self:
        return cls(node_ids=ids, deselect=deselect)


@dataclass(frozen=True)
class SuiteRun:
    results: tuple[NodeResult, ...]
    timed_out: bool = False


@dataclass(frozen=True)
class SandboxContext:
    tree: Path
    output_dir: Path
    env: ScrubbedEnvironment
    runner: ProcessRunner
    install_timeout_s: float
    suite_timeout_s: float


class BenchmarkAdapter(Protocol):
    language: SourceLanguage

    def resolve_environment(self, ctx: SandboxContext) -> EnvironmentIdentity: ...

    def path_entries(self, ctx: SandboxContext) -> tuple[Path, ...]: ...

    def run_suite(self, ctx: SandboxContext, selection: SuiteSelection) -> SuiteRun: ...
