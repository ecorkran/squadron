"""The services ``sq benchmark judge`` is given: the command's one seam (slice 426 D12-D16).

The CLI fills this with the real collaborators; command tests substitute doubles, so no test
runs a model. Nothing here chooses what to judge.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from squadron.benchmark.diff_judge import DiffSidecarWriter
from squadron.benchmark.diff_judge_plan import ResolvedJudge
from squadron.core.process_runner import ProcessRunner
from squadron.metrology.benchmark_store import BenchmarkRecordStore
from squadron.metrology.slice_case_store import SliceCaseRecordStore
from squadron.replay.judging import JudgeDispatcher


@dataclass(frozen=True)
class JudgeServices:
    repo_root: Path
    store: BenchmarkRecordStore
    slice_store: SliceCaseRecordStore
    process_runner: ProcessRunner
    #: Where the judge lock lives.
    lock_root: Path
    clock: Callable[[], datetime]
    #: A config value by key, for the caller's repository.
    read_config: Callable[[str], object]
    #: The judge for an alias, or an error naming why it cannot be called.
    resolve_judge: Callable[[str], ResolvedJudge]
    #: A dispatcher for an alias, resolved once so a bad alias fails before any call.
    dispatcher_for: Callable[[str], JudgeDispatcher]
    #: Where normalized diffs are stored (the ``diffs`` sidecar kind).
    sidecars: DiffSidecarWriter
    #: The project id of a checkout, as cases record it.
    project_id_of: Callable[[Path], str]
