"""Build slice cases from a project's recorded landings (slice 426 D1, D6, API Contracts).

Discovery sorts every slice in the ``slice_ranges`` record, qualification turns each candidate
into a stored result, and the qualified cases join the named case set. One line per slice
index comes back; a harness error stops the build, and each later index is reported as not
attempted with no record, so no index is silently dropped.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from squadron.benchmark.build_errors import BuildHalted
from squadron.benchmark.slice_discovery import (
    DiscoveryResult,
    SliceCandidate,
    SliceHarnessFailure,
    SliceRangeSource,
    SliceRejection,
    discover,
)
from squadron.benchmark.slice_qualify import (
    UNKNOWN_SLICE_NAME,
    qualify_slice_candidate,
    record_slice_outcome,
)
from squadron.benchmark.slice_qualify_types import SliceQualifyDeps, SliceQualifyResult
from squadron.metrology.benchmark_models import CaseSet, QualificationOutcome
from squadron.metrology.errors import MetrologyStoreError
from squadron.metrology.slice_case_models import SliceQualification

_logger = logging.getLogger(__name__)

NOT_ATTEMPTED = "slice {index} not attempted (build stopped at slice {stopped})"


class CaseSetStore(Protocol):
    def get_case_set(self, name: str, version: int | None = None) -> CaseSet | None: ...

    def write_case_set(self, name: str, case_ids: list[str] | tuple[str, ...]) -> CaseSet: ...


@dataclass(frozen=True)
class SliceBuildDeps:
    qualify: SliceQualifyDeps
    ranges: SliceRangeSource
    case_sets: CaseSetStore


@dataclass(frozen=True)
class SliceBuildResult:
    """Every line printed, the case set written (``None`` when it would be empty), the slice
    that stopped the build (``None`` when it finished) and the sandbox trees ``keep`` left."""

    lines: tuple[str, ...]
    case_set: CaseSet | None
    stopped_at: int | None
    kept_paths: tuple[Path, ...]


#: One slice of the record, whichever way discovery sorted it.
_Entry = SliceCandidate | SliceRejection | SliceHarnessFailure


def build_slice_cases(
    repo: Path, set_name: str, deps: SliceBuildDeps, on_line: Callable[[str], None]
) -> SliceBuildResult:
    """Discover, qualify every candidate and write the case set; ``on_line`` sees each line."""
    qualify = deps.qualify
    discovered = discover(deps.ranges, qualify.project_id, qualify.runner, repo, qualify.git_timeout_s)
    lines: list[str] = []
    kept: list[Path] = []
    qualified: list[str] = []
    stopped_at: int | None = None

    def emit(line: str) -> None:
        lines.append(line)
        on_line(line)

    for index, entry in _in_index_order(discovered):
        if stopped_at is not None:
            emit(NOT_ATTEMPTED.format(index=index, stopped=stopped_at))
            continue
        record, paths = _settle(entry, qualify)
        kept.extend(paths)
        emit(describe(record))
        if record.case_id is not None:
            qualified.append(record.case_id)
        if record.outcome is QualificationOutcome.HARNESS_ERROR:
            stopped_at = index
    return SliceBuildResult(
        tuple(lines), _write_case_set(deps.case_sets, set_name, qualified), stopped_at, tuple(kept)
    )


def describe(record: SliceQualification) -> str:
    """The line a slice prints: its outcome and detail. A reused record reads as a fresh one."""
    prefix = f"slice {record.slice_index}"
    match record.outcome:
        case QualificationOutcome.QUALIFIED:
            return f"{prefix} qualified {record.case_id} ({record.detail})"
        case QualificationOutcome.REJECTED:
            reason = record.rejection.value if record.rejection else "rejected"
            return f"{prefix} {reason}: {record.detail}"
        case QualificationOutcome.HARNESS_ERROR:
            return f"{prefix} harness_error: {record.detail}"


def _in_index_order(discovered: DiscoveryResult) -> list[tuple[int, _Entry]]:
    entries: list[tuple[int, _Entry]] = [
        *((item.slice_index, item) for item in discovered.candidates),
        *((item.slice_index, item) for item in discovered.rejections),
        *((item.slice_index, item) for item in discovered.harness_failures),
    ]
    return sorted(entries, key=lambda pair: pair[0])


def _settle(entry: _Entry, qualify: SliceQualifyDeps) -> tuple[SliceQualification, tuple[Path, ...]]:
    """The stored result for one entry: qualified now, or recorded from discovery."""
    if isinstance(entry, SliceCandidate):
        result: SliceQualifyResult = qualify_slice_candidate(entry, qualify)
        return result.record, result.kept_paths
    if isinstance(entry, SliceRejection):
        record = record_slice_outcome(
            qualify,
            entry.slice_index,
            entry.landing,
            UNKNOWN_SLICE_NAME,
            QualificationOutcome.REJECTED,
            rejection=entry.rejection,
            detail=entry.detail,
        )
        return record, ()
    record = record_slice_outcome(
        qualify,
        entry.slice_index,
        entry.landing,
        UNKNOWN_SLICE_NAME,
        QualificationOutcome.HARNESS_ERROR,
        detail=entry.detail,
    )
    return record, ()


def _write_case_set(store: CaseSetStore, name: str, qualified: Sequence[str]) -> CaseSet | None:
    """The set holds the earlier members and this build's qualified cases; empty writes nothing."""
    try:
        existing = store.get_case_set(name)
        members = sorted({*(existing.case_ids if existing else ()), *qualified})
        if not members:
            return None
        return store.write_case_set(name, members)
    except MetrologyStoreError as exc:
        message = f"could not write case set '{name}': {exc}"
        _logger.exception(message)
        raise BuildHalted(message) from exc
