"""Collaborators and errors of one replay (slice 424): everything ``replay_one`` is handed."""

from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Protocol

from squadron.benchmark.bench_plan import BenchConfig, Caps
from squadron.benchmark.case_runners import CaseKindRunner, ReplaySandbox
from squadron.benchmark.leak_scan import LeakRules
from squadron.benchmark.transcripts import TranscriptSource
from squadron.core.process_runner import ProcessRunner
from squadron.metrology.benchmark_models import (
    BenchmarkCase,
    CandidateRejection,
    CaseKind,
    FixQualification,
)
from squadron.metrology.benchmark_replay_models import ImplementationReplay
from squadron.metrology.diff_sidecars import DiffSidecars
from squadron.metrology.replay_models import ProducerConfigRef
from squadron.pipeline.state import RunState
from squadron.providers.base import ProfileName

_logger = logging.getLogger(__name__)


class ReplayStoreError(Exception):
    """A step after the producer could not be stored; the sandbox was kept, nothing recorded."""


class ReplayStore(Protocol):
    diffs: DiffSidecars

    def write_replay(self, record_id: str, replay: ImplementationReplay) -> str: ...


class RunStateReader(Protocol):
    def load(self, run_id: str) -> RunState: ...


#: ``(case id, environment digest)`` -> what re-qualification said; shared across replays.
RequalifyCache = dict[tuple[str, str], FixQualification | CandidateRejection]


@dataclass(frozen=True)
class ReplayOneDeps:
    benchmark_id: str
    case_set: str
    case_set_version: int
    caps: Caps
    #: ``--keep``: leave the sandbox in place after a written record.
    keep: bool
    git_timeout_s: float
    sandbox_factory: Callable[[BenchmarkCase], AbstractContextManager[ReplaySandbox]]
    runners: Callable[[CaseKind], CaseKindRunner | None]
    store: ReplayStore
    state_reader_for: Callable[[Path], RunStateReader]
    transcript_sources: Callable[[ProfileName], TranscriptSource | None]
    leak_rules_for: Callable[[ReplaySandbox, BenchmarkCase], LeakRules]
    config_ref_for: Callable[[BenchConfig], ProducerConfigRef]
    process_runner: ProcessRunner
    clock: Callable[[], datetime]
    requalify_cache: RequalifyCache = field(default_factory=RequalifyCache)


def store_failure(sandbox: ReplaySandbox | None, message: str) -> ReplayStoreError:
    """Log at ERROR, keep the sandbox for inspection, and return the error to raise."""
    _logger.error("%s%s", message, "" if sandbox is None else f"; sandbox kept at {sandbox.tree}")
    if sandbox is not None:
        sandbox.keep()
    return ReplayStoreError(message)
