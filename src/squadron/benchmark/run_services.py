"""The services ``sq benchmark run`` is given (slice 424): the command's one dependency seam.

``build_production_services`` (``production_deps``) fills this with the real collaborators;
command tests substitute doubles, so no test runs a model, a sandbox or git.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from squadron.benchmark.auth_check import AuthAnswer
from squadron.benchmark.bench_plan import Caps
from squadron.benchmark.bench_runner import OrphanSweep, ReplayFunction
from squadron.benchmark.case_runners import CaseKindRunner
from squadron.benchmark.transcripts import TranscriptSource
from squadron.core.process_runner import ProcessRunner
from squadron.metrology.benchmark_models import CaseKind
from squadron.metrology.benchmark_store import BenchmarkRecordStore
from squadron.providers.base import ProfileName


@dataclass(frozen=True)
class ReplayContext:
    """What identifies one benchmark invocation to the replay driver."""

    benchmark_id: str
    case_set: str
    case_set_version: int
    caps: Caps
    keep: bool


@dataclass(frozen=True)
class KeptSandbox:
    """A sandbox still on disk after the run: left by ``--keep`` or by a store failure."""

    tree: Path
    home: Path
    output_dir: Path


@dataclass(frozen=True)
class RunServices:
    repo_root: Path
    store: BenchmarkRecordStore
    process_runner: ProcessRunner
    #: Where benchmark locks and sandboxes live.
    lock_root: Path
    sweep: OrphanSweep
    clock: Callable[[], datetime]
    runners: Callable[[CaseKind], CaseKindRunner | None]
    transcript_sources: Callable[[ProfileName], TranscriptSource | None]
    #: A harness config value by key, ``None`` when unset.
    read_config: Callable[[str], object | None]
    #: The auth check's answer per profile for the given aliases.
    auth_check: Callable[[Sequence[str]], Mapping[ProfileName, AuthAnswer]]
    #: Aliases whose replays report no cost, so the bound cannot cover them.
    unpriced_aliases: Callable[[Sequence[str]], frozenset[str]]
    replay_function: Callable[[ReplayContext], ReplayFunction]
    #: The sandboxes this invocation created that are still on disk.
    kept_sandboxes: Callable[[], Sequence[KeptSandbox]]
