"""Benchmark case and case-set record I/O (slice 421 D1-D3).

Lives beside ``MetrologyStore`` rather than inside it: benchmark records will keep
growing over initiative 420, and ``store.py`` is already large. It uses the store's public
``write_record`` and ``iter_records`` primitives and ``load_record``.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from squadron.metrology.benchmark_models import (
    BenchmarkCase,
    CaseSet,
    FixQualification,
    case_set_record_id,
    fix_qualification_record_id,
)
from squadron.metrology.errors import MetrologyStoreError
from squadron.metrology.models import (
    RECORD_TYPE_BENCHMARK_CASE,
    RECORD_TYPE_CASE_SET,
    RECORD_TYPE_FIX_QUALIFICATION,
    MetrologyRecord,
    ProjectId,
)
from squadron.metrology.store import MetrologyStore, SchemaVersionError

_logger = logging.getLogger(__name__)
_SCHEMA_VERSION = 1


class BenchmarkRecordStore:
    """Cases and versioned case sets over a ``MetrologyStore``."""

    def __init__(self, store: MetrologyStore) -> None:
        self._store = store

    # ------------------------------------------------------------------ cases

    def write_case(self, case: BenchmarkCase) -> str:
        """Persist *case* once; an identical case written again returns the same id."""
        if not self._store.record_location(case.case_id).exists():
            self._store.write_record(
                case.case_id,
                MetrologyRecord(
                    schema_version=_SCHEMA_VERSION,
                    record_type=RECORD_TYPE_BENCHMARK_CASE,
                    benchmark_case=case,
                ),
            )
        return case.case_id

    def get_case(self, case_id: str) -> BenchmarkCase | None:
        """The stored case, ``None`` when absent; a tampered or foreign record raises."""
        record = self._load(case_id)
        if record is None:
            return None
        if record.record_type != RECORD_TYPE_BENCHMARK_CASE or record.benchmark_case is None:
            _logger.error("record %s is not a benchmark case", case_id)
            raise MetrologyStoreError(f"Record {case_id} is not a benchmark case")
        return record.benchmark_case

    def list_cases(self, project_id: ProjectId) -> list[BenchmarkCase]:
        """Cases of one project; an unreadable or mismatching file warns and is skipped."""
        cases = [
            record.benchmark_case
            for _, record in self._store.iter_records()
            if record.benchmark_case is not None
            and record.benchmark_case.project_id.value == project_id.value
        ]
        return sorted(cases, key=lambda case: case.case_id)

    # -------------------------------------------------------------- case sets

    def write_case_set(self, name: str, case_ids: list[str] | tuple[str, ...]) -> CaseSet:
        """Write version latest + 1 when the list changed; return the existing one if not."""
        wanted = CaseSet(name=name, version=1, case_ids=tuple(case_ids), created_at=_now())
        missing = [cid for cid in wanted.case_ids if self.get_case(cid) is None]
        if missing:
            raise MetrologyStoreError(f"Case set '{name}' names unknown case ids: {missing}")
        while True:
            latest = self.get_case_set(name)
            if latest is not None and latest.case_ids == wanted.case_ids:
                return latest
            next_version = 1 if latest is None else latest.version + 1
            created = wanted.model_copy(update={"version": next_version})
            try:
                self._store.create_record(
                    created.record_id,
                    MetrologyRecord(
                        schema_version=_SCHEMA_VERSION,
                        record_type=RECORD_TYPE_CASE_SET,
                        case_set=created,
                    ),
                )
            except FileExistsError:
                # A concurrent writer took this version; re-read and compare against it.
                continue
            return created

    def get_case_set(self, name: str, version: int | None = None) -> CaseSet | None:
        """The named set at *version* (latest when ``None``); ``None`` when absent."""
        if version is not None:
            return self._load_case_set(name, version)
        latest: CaseSet | None = None
        next_version = 1
        while (found := self._load_case_set(name, next_version)) is not None:
            latest = found
            next_version += 1
        return latest

    def list_case_sets(self) -> list[CaseSet]:
        """Every stored version of every set, sorted by name then version."""
        sets = [
            record.case_set for _, record in self._store.iter_records() if record.case_set is not None
        ]
        return sorted(sets, key=lambda case_set: (case_set.name, case_set.version))

    # ------------------------------------------------------ fix qualifications

    def write_fix_qualification(self, qualification: FixQualification) -> str:
        """Persist *qualification*; a newer result under the same key replaces the older."""
        record_id = qualification.record_id
        self._store.write_record(
            record_id,
            MetrologyRecord(
                schema_version=_SCHEMA_VERSION,
                record_type=RECORD_TYPE_FIX_QUALIFICATION,
                fix_qualification=qualification,
            ),
        )
        return record_id

    def get_fix_qualification(
        self, project_id: ProjectId, commit_sha: str, env_digest: str | None
    ) -> FixQualification | None:
        """The stored result for the key, ``None`` when absent; a tampered or foreign file raises."""
        record_id = fix_qualification_record_id(project_id, commit_sha, env_digest)
        record = self._load(record_id)
        if record is None:
            return None
        if record.record_type != RECORD_TYPE_FIX_QUALIFICATION or record.fix_qualification is None:
            _logger.error("record %s is not a fix qualification", record_id)
            raise MetrologyStoreError(f"Record {record_id} is not a fix qualification")
        return record.fix_qualification

    def list_fix_qualifications(self, project_id: ProjectId | None = None) -> list[FixQualification]:
        """Every stored result, of one project when given; unreadable files warn and are skipped."""
        found = [
            record.fix_qualification
            for _, record in self._store.iter_records()
            if record.fix_qualification is not None
            and (project_id is None or record.fix_qualification.project_id.value == project_id.value)
        ]
        return sorted(found, key=lambda item: item.record_id)

    # ---------------------------------------------------------------- helpers

    def _load_case_set(self, name: str, version: int) -> CaseSet | None:
        record_id = case_set_record_id(name, version)
        record = self._load(record_id)
        if record is None:
            return None
        if record.record_type != RECORD_TYPE_CASE_SET or record.case_set is None:
            _logger.error("record %s is not a case set", record_id)
            raise MetrologyStoreError(f"Record {record_id} is not a case set")
        return record.case_set

    def _load(self, record_id: str) -> MetrologyRecord | None:
        """Load one record: absent is ``None``; unreadable, tampered or foreign raises."""
        try:
            return self._store.load_record(record_id)
        except FileNotFoundError:
            return None
        except (ValueError, SchemaVersionError, OSError) as exc:
            # ValueError covers JSON errors and pydantic's ValidationError (a tampered file).
            _logger.exception("unreadable benchmark record %s", record_id)
            raise MetrologyStoreError(f"Unreadable benchmark record {record_id}: {exc}") from exc


def _now() -> datetime:
    return datetime.now(UTC)
