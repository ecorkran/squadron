"""Slice-case records over the benchmark store (slice 426, Database / Storage Schema).

``SliceCaseRecordStore`` adds the slice qualification, diff judgment and over-size record
methods beside 421's ``BenchmarkRecordStore``, as ``GradeRecordStore`` does for grades. A
write that fails is logged at ERROR and raises the store's error; a record of another type
under a slice-case id raises rather than being read as absent.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator

from squadron.metrology.benchmark_store import BenchmarkRecordStore
from squadron.metrology.errors import MetrologyStoreError
from squadron.metrology.models import (
    RECORD_TYPE_DIFF_JUDGMENT,
    RECORD_TYPE_OVER_SIZE_CASE,
    RECORD_TYPE_SLICE_QUALIFICATION,
    MetrologyRecord,
    ProjectId,
)
from squadron.metrology.slice_case_models import (
    DiffJudgment,
    OverSizeCase,
    SliceQualification,
    slice_qualification_id,
)
from squadron.metrology.store import SchemaVersionError

_logger = logging.getLogger(__name__)
_SCHEMA_VERSION = 1


class SliceCaseRecordStore:
    """Slice qualifications, diff judgments and over-size case records."""

    def __init__(self, records: BenchmarkRecordStore) -> None:
        self._store = records.metrology_store

    # --------------------------------------------------------- qualifications

    def write_slice_qualification(self, qualification: SliceQualification) -> str:
        """Persist *qualification*; a newer result under the same key replaces the older."""
        return self._write(
            qualification.record_id,
            MetrologyRecord(
                schema_version=_SCHEMA_VERSION,
                record_type=RECORD_TYPE_SLICE_QUALIFICATION,
                slice_qualification=qualification,
            ),
        )

    def get_slice_qualification(
        self, project_id: ProjectId, slice_index: int, after_sha: str, env_digest: str | None
    ) -> SliceQualification | None:
        """The stored result for the key; ``env_digest=None`` addresses the pre-sandbox record."""
        record_id = slice_qualification_id(project_id, slice_index, after_sha, env_digest)
        record = self._load(record_id)
        if record is None:
            return None
        if record.record_type != RECORD_TYPE_SLICE_QUALIFICATION or record.slice_qualification is None:
            self._not_a(record_id, "slice qualification")
        return record.slice_qualification

    def list_slice_qualifications(
        self, project_id: ProjectId | None = None
    ) -> list[SliceQualification]:
        """Every stored result, of one project when given; unreadable files warn and are skipped."""
        found = [
            record.slice_qualification
            for _, record in self._store.iter_records()
            if record.slice_qualification is not None
            and (project_id is None or record.slice_qualification.project_id.value == project_id.value)
        ]
        return sorted(found, key=lambda item: item.record_id)

    # -------------------------------------------------------- diff judgments

    def write_diff_judgment(self, judgment: DiffJudgment) -> str:
        """Persist *judgment*; the id carries the pair and the judge, so a rerun cannot duplicate."""
        return self._write(
            judgment.record_id,
            MetrologyRecord(
                schema_version=_SCHEMA_VERSION,
                record_type=RECORD_TYPE_DIFF_JUDGMENT,
                diff_judgment=judgment,
            ),
        )

    def diff_judgments_for(
        self, benchmark_id: str, judge_alias: str | None = None
    ) -> list[DiffJudgment]:
        """One benchmark's judgments, of one judge alias when given, sorted by record id."""
        found = [
            judgment
            for judgment in self._judgments()
            if judgment.benchmark_id == benchmark_id
            and (judge_alias is None or judgment.judge.alias == judge_alias)
        ]
        return sorted(found, key=lambda item: item.record_id)

    def diff_judgments_by(self, judge_alias: str) -> list[DiffJudgment]:
        """Every benchmark's judgments by one judge alias, sorted by record id (one store scan)."""
        found = [item for item in self._judgments() if item.judge.alias == judge_alias]
        return sorted(found, key=lambda item: item.record_id)

    def _judgments(self) -> Iterator[DiffJudgment]:
        for _, record in self._store.iter_records():
            if record.diff_judgment is not None:
                yield record.diff_judgment

    # ------------------------------------------------------- over-size cases

    def write_over_size_case(self, over_size: OverSizeCase) -> str:
        """Persist *over_size*; written again under the same id it is replaced (the limit moved)."""
        return self._write(
            over_size.record_id,
            MetrologyRecord(
                schema_version=_SCHEMA_VERSION,
                record_type=RECORD_TYPE_OVER_SIZE_CASE,
                over_size_case=over_size,
            ),
        )

    def over_size_cases_for(
        self, benchmark_id: str, judge_alias: str | None = None
    ) -> list[OverSizeCase]:
        """One benchmark's over-size records, of one judge alias when given, sorted by id."""
        found = [
            record.over_size_case
            for _, record in self._store.iter_records()
            if record.over_size_case is not None
            and record.over_size_case.benchmark_id == benchmark_id
            and (judge_alias is None or record.over_size_case.judge.alias == judge_alias)
        ]
        return sorted(found, key=lambda item: item.record_id)

    # ---------------------------------------------------------------- helpers

    def _write(self, record_id: str, record: MetrologyRecord) -> str:
        """Write one record; a failure is logged at ERROR and re-raised."""
        try:
            self._store.write_record(record_id, record)
        except MetrologyStoreError:
            _logger.exception("Failed to write slice-case record %s", record_id)
            raise
        return record_id

    def _load(self, record_id: str) -> MetrologyRecord | None:
        """Load one record: absent is ``None``; unreadable, tampered or foreign raises."""
        try:
            return self._store.load_record(record_id)
        except FileNotFoundError:
            return None
        except (ValueError, SchemaVersionError, OSError) as exc:
            _logger.exception("unreadable slice-case record %s", record_id)
            raise MetrologyStoreError(f"Unreadable slice-case record {record_id}: {exc}") from exc

    @staticmethod
    def _not_a(record_id: str, kind: str) -> None:
        _logger.error("record %s is not a %s", record_id, kind)
        raise MetrologyStoreError(f"Record {record_id} is not a {kind}")
