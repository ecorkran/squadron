"""Grade and estimate records over the benchmark store (slice 425 D10, State Management).

``GradeRecordStore`` adds the grade record methods beside 421's ``BenchmarkRecordStore``
(whose sidecars it reaches through ``records``). A grade record is bounded: one over
``MAX_GRADE_RECORD_BYTES`` is refused loudly, never truncated.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from typing import Any, NoReturn

from squadron.metrology.benchmark_models import CASE_ID_PREFIX
from squadron.metrology.benchmark_replay_models import REPLAY_ID_PREFIX
from squadron.metrology.benchmark_store import BenchmarkRecordStore
from squadron.metrology.errors import MetrologyStoreError
from squadron.metrology.grade_records import (
    ImplementationGrade,
    ReferenceGrade,
    SampleSizeEstimate,
)
from squadron.metrology.models import (
    RECORD_TYPE_IMPLEMENTATION_GRADE,
    RECORD_TYPE_REFERENCE_GRADE,
    RECORD_TYPE_SAMPLE_SIZE_ESTIMATE,
    MetrologyRecord,
)
from squadron.metrology.store import SchemaVersionError

_logger = logging.getLogger(__name__)

MAX_GRADE_RECORD_BYTES = 16 * 1024
REFERENCE_GRADE_ID_PREFIX = "refgrade-"
IMPLEMENTATION_GRADE_ID_PREFIX = "implgrade-"
ESTIMATE_ID_PREFIX = "estimate-"
_SCHEMA_VERSION = 1
_CASE_SEGMENT_DIGITS = 12
_REFERENCE_GRADER_DIGITS = 12
_REFERENCE_ENVIRONMENT_DIGITS = 8
_IMPLEMENTATION_GRADER_DIGITS = 8
_GRADE_RECORD_TYPES = (RECORD_TYPE_REFERENCE_GRADE, RECORD_TYPE_IMPLEMENTATION_GRADE)


def reference_grade_id(case_id: str, grader_digest: str, environment_digest: str) -> str:
    """``refgrade-<case id 12>-<grader digest 12>-<environment digest 8>``."""
    if not case_id.startswith(CASE_ID_PREFIX):
        raise ValueError(f"case id {case_id!r} does not start with {CASE_ID_PREFIX!r}")
    case_segment = case_id.removeprefix(CASE_ID_PREFIX)[:_CASE_SEGMENT_DIGITS]
    return (
        f"{REFERENCE_GRADE_ID_PREFIX}{case_segment}"
        f"-{grader_digest[:_REFERENCE_GRADER_DIGITS]}"
        f"-{environment_digest[:_REFERENCE_ENVIRONMENT_DIGITS]}"
    )


def implementation_grade_id(replay_id: str, grader_digest: str) -> str:
    """``implgrade-<replay id without its prefix>-<grader digest 8>``."""
    if not replay_id.startswith(REPLAY_ID_PREFIX):
        raise ValueError(f"replay id {replay_id!r} does not start with {REPLAY_ID_PREFIX!r}")
    stem = replay_id.removeprefix(REPLAY_ID_PREFIX)
    return f"{IMPLEMENTATION_GRADE_ID_PREFIX}{stem}-{grader_digest[:_IMPLEMENTATION_GRADER_DIGITS]}"


def estimate_id(benchmark_id: str) -> str:
    """One estimate record per benchmark: the id carries nothing else."""
    return f"{ESTIMATE_ID_PREFIX}{benchmark_id}"


def _largest_field(payload: dict[str, Any]) -> str:
    """Name of the biggest serialized field, looking one level into nested objects."""
    sizes: dict[str, int] = {}
    for name, value in payload.items():
        if isinstance(value, dict):
            nested: dict[str, Any] = value  # pyright: ignore[reportUnknownVariableType]
            for inner_name, inner_value in nested.items():
                sizes[f"{name}.{inner_name}"] = len(json.dumps(inner_value))
        else:
            sizes[name] = len(json.dumps(value))
    return max(sizes, key=lambda key: sizes[key])


class GradeRecordStore:
    """Reference grades, implementation grades and sample-size estimates."""

    def __init__(self, records: BenchmarkRecordStore) -> None:
        self._records = records
        self._store = records.metrology_store
        # The sidecars a grade writes, reached through the same object that writes its record.
        self.diffs = records.diffs
        self.snapshots = records.snapshots
        self.nodes = records.nodes
        self.reviews = records.reviews

    # ------------------------------------------------------------ references

    def write_reference_grade(self, grade: ReferenceGrade) -> str:
        record_id = reference_grade_id(grade.case_id, grade.grader.digest, grade.environment_digest)
        self._write_once(
            record_id,
            self._get_reference(record_id),
            grade,
            MetrologyRecord(
                schema_version=_SCHEMA_VERSION,
                record_type=RECORD_TYPE_REFERENCE_GRADE,
                reference_grade=grade,
            ),
            grade.model_dump(mode="json"),
        )
        return record_id

    def get_reference_grade(
        self, case_id: str, grader_digest: str, environment_digest: str
    ) -> ReferenceGrade | None:
        """The case's reference under this grader and environment, whichever benchmark wrote it."""
        record_id = reference_grade_id(case_id, grader_digest, environment_digest)
        grade = self._get_reference(record_id)
        if grade is None:
            return None
        if (
            grade.case_id != case_id
            or grade.grader.digest != grader_digest
            or grade.environment_digest != environment_digest
        ):
            # The id carries truncated digests; a different grade under it is a collision.
            _logger.error("reference grade %s does not match the lookup key", record_id)
            raise MetrologyStoreError(f"Reference grade {record_id} does not match its key")
        return grade

    def _get_reference(self, record_id: str) -> ReferenceGrade | None:
        record = self._load(record_id)
        if record is None:
            return None
        if record.record_type != RECORD_TYPE_REFERENCE_GRADE or record.reference_grade is None:
            self._not_a(record_id, "reference grade")
        return record.reference_grade

    # ----------------------------------------------------------- replays

    def write_grade(self, grade: ImplementationGrade) -> str:
        record_id = implementation_grade_id(grade.replay_id, grade.grader.digest)
        self._write_once(
            record_id,
            self.get_grade(record_id),
            grade,
            MetrologyRecord(
                schema_version=_SCHEMA_VERSION,
                record_type=RECORD_TYPE_IMPLEMENTATION_GRADE,
                implementation_grade=grade,
            ),
            grade.model_dump(mode="json"),
        )
        return record_id

    def get_grade(self, record_id: str) -> ImplementationGrade | None:
        record = self._load(record_id)
        if record is None:
            return None
        if (
            record.record_type != RECORD_TYPE_IMPLEMENTATION_GRADE
            or record.implementation_grade is None
        ):
            self._not_a(record_id, "implementation grade")
        return record.implementation_grade

    def grades_for(self, benchmark_id: str) -> list[tuple[str, ImplementationGrade]]:
        """``(record_id, grade)`` of one benchmark's implementation grades, sorted by id."""
        found = [
            (record_id, record.implementation_grade)
            for record_id, record in self._store.iter_records()
            if record.implementation_grade is not None
            and record.implementation_grade.benchmark_id == benchmark_id
        ]
        return sorted(found, key=lambda item: item[0])

    def delete_grades(self, record_ids: Sequence[str]) -> int:
        """Remove the named reference and implementation grade records (``--retry-harness``).

        Returns how many existed. A record of any other type under a named id raises.
        """
        removed = 0
        for record_id in record_ids:
            record = self._load(record_id)
            if record is None:
                continue
            if record.record_type not in _GRADE_RECORD_TYPES:
                self._not_a(record_id, "grade")
            if self._store.delete_record(record_id):
                removed += 1
        return removed

    # ---------------------------------------------------------- estimates

    def write_estimate(self, estimate: SampleSizeEstimate) -> str:
        """Write the benchmark's one estimate, replacing the earlier one."""
        record_id = estimate_id(estimate.benchmark_id)
        record = MetrologyRecord(
            schema_version=_SCHEMA_VERSION,
            record_type=RECORD_TYPE_SAMPLE_SIZE_ESTIMATE,
            sample_size_estimate=estimate,
        )
        self._persist(record_id, record, estimate.model_dump(mode="json"))
        return record_id

    def estimate_for(self, benchmark_id: str) -> SampleSizeEstimate | None:
        """The estimate this benchmark wrote, ``None`` when it has none."""
        record_id = estimate_id(benchmark_id)
        record = self._load(record_id)
        if record is None:
            return None
        if (
            record.record_type != RECORD_TYPE_SAMPLE_SIZE_ESTIMATE
            or record.sample_size_estimate is None
        ):
            self._not_a(record_id, "sample-size estimate")
        return record.sample_size_estimate

    def latest_estimate(self, case_set: str) -> SampleSizeEstimate | None:
        """The newest estimate over *case_set*, by ``created_at``."""
        matches = [
            record.sample_size_estimate
            for _, record in self._store.iter_records()
            if record.sample_size_estimate is not None
            and record.sample_size_estimate.case_set == case_set
        ]
        return max(matches, key=lambda estimate: estimate.created_at, default=None)

    def largest_review_cost(self, reviewer_key: str) -> float | None:
        """The largest priced review cost among stored grades by this reviewer, ``None`` if none.

        The per-review figure of a grade bound (D9): what the most expensive observed review of
        the same reviewer cost, across reference and implementation grades.
        """
        costs: list[float] = []
        for _, record in self._store.iter_records():
            grade = record.reference_grade or record.implementation_grade
            if grade is None or grade.result is None:
                continue
            if grade.grader.reviewer.reviewer_key != reviewer_key:
                continue
            costs.extend(r.cost_usd for r in grade.result.reviews if r.cost_usd is not None)
        return max(costs, default=None)

    # ------------------------------------------------------------ helpers

    def _write_once(
        self,
        record_id: str,
        existing: ReferenceGrade | ImplementationGrade | None,
        grade: ReferenceGrade | ImplementationGrade,
        record: MetrologyRecord,
        payload: dict[str, Any],
    ) -> None:
        if existing is not None:
            if existing == grade:
                return
            _logger.error("grade record %s already exists with different content", record_id)
            raise MetrologyStoreError(f"Grade record {record_id} already exists and differs")
        self._persist(record_id, record, payload)

    def _persist(self, record_id: str, record: MetrologyRecord, payload: dict[str, Any]) -> None:
        """Refuse an oversized record, then write; failures are logged at ERROR and raised."""
        size = len(record.model_dump_json().encode("utf-8"))
        if size > MAX_GRADE_RECORD_BYTES:
            largest = _largest_field(payload)
            _logger.error(
                "grade record %s is %d bytes, over the %d-byte bound; largest field: %s",
                record_id,
                size,
                MAX_GRADE_RECORD_BYTES,
                largest,
            )
            raise MetrologyStoreError(
                f"Grade record {record_id} is {size} bytes, over the "
                f"{MAX_GRADE_RECORD_BYTES}-byte bound (largest field: {largest})"
            )
        try:
            self._store.write_record(record_id, record)
        except MetrologyStoreError:
            _logger.exception("Failed to write grade record %s", record_id)
            raise

    def _load(self, record_id: str) -> MetrologyRecord | None:
        """Absent is ``None``; unreadable, tampered or foreign raises."""
        try:
            return self._store.load_record(record_id)
        except FileNotFoundError:
            return None
        except (ValueError, SchemaVersionError, OSError) as exc:
            _logger.exception("unreadable grade record %s", record_id)
            raise MetrologyStoreError(f"Unreadable grade record {record_id}: {exc}") from exc

    @staticmethod
    def _not_a(record_id: str, kind: str) -> NoReturn:
        _logger.error("record %s is not a %s", record_id, kind)
        raise MetrologyStoreError(f"Record {record_id} is not a {kind}")
