"""Read and write the four recall record types over a ``MetrologyStore`` (slice 430 D4).

Wraps the store as ``BenchmarkRecordStore`` does, using its public ``write_record``,
``create_record``, ``load_record`` and ``iter_records`` primitives. Case and import label
records are written once; run records and person label records are rewritten in place.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Iterable
from datetime import datetime

from squadron.metrology.content_sidecars import ContentSidecars, SidecarKind
from squadron.metrology.errors import MetrologyStoreError
from squadron.metrology.models import (
    RECORD_TYPE_RECALL_CASE,
    RECORD_TYPE_RECALL_CASE_SET,
    RECORD_TYPE_RECALL_LABELS,
    RECORD_TYPE_RECALL_RUN,
    RECORD_TYPE_RECIPE_REVIEW,
    MetrologyRecord,
)
from squadron.metrology.recall_case_models import RealBugCase, RecallCaseSet, case_set_id
from squadron.metrology.recall_label_models import RecallLabels, labels_record_id
from squadron.metrology.recall_run_models import RecallRun, run_record_id
from squadron.metrology.recipe_review_models import RecipeReview
from squadron.metrology.store import MetrologyStore, SchemaVersionError

_logger = logging.getLogger(__name__)
_SCHEMA_VERSION = 1
_SET_REF = re.compile(r"^\s*(?P<name>[^@\s]+)\s*(?:@\s*v?(?P<version>\d+))?\s*$")

Clock = Callable[[], datetime]


class RecallStoreError(MetrologyStoreError):
    """A recall record is missing, foreign or malformed."""


def parse_set_ref(ref: str) -> tuple[str, int | None]:
    """``name`` or ``name@N`` (``name@vN`` too) to ``(name, version or None)``."""
    match = _SET_REF.match(ref)
    if match is None:
        raise ValueError(f"case set reference {ref!r} is not NAME or NAME@VERSION")
    version = match.group("version")
    return match.group("name"), None if version is None else int(version)


class RecallRecordStore:
    """Cases, case sets, run records and label records of reviewer recall."""

    def __init__(self, store: MetrologyStore, clock: Clock) -> None:
        self._store = store
        self._clock = clock
        #: Raw review and comb output, by sha256 (D4).
        self.reviews = ContentSidecars(store.store_dir, SidecarKind.REVIEWS)

    # ------------------------------------------------------------------ cases

    def write_case(self, case: RealBugCase) -> bool:
        """Persist *case* once; returns ``True`` when it was new."""
        if self._store.record_location(case.case_id).exists():
            return False
        self._write(case.case_id, _envelope(RECORD_TYPE_RECALL_CASE, recall_case=case))
        return True

    def get_case(self, case_id: str) -> RealBugCase | None:
        record = self._load(case_id, RECORD_TYPE_RECALL_CASE)
        return None if record is None else record.recall_case

    def list_cases(self) -> list[RealBugCase]:
        cases = [r.recall_case for r in self._iter(RECORD_TYPE_RECALL_CASE) if r.recall_case]
        return sorted(cases, key=lambda case: (case.name, case.case_id))

    # -------------------------------------------------------------- case sets

    def write_case_set(self, name: str, case_ids: Iterable[str]) -> RecallCaseSet:
        """Write version latest + 1 when membership changed; else return the latest."""
        wanted = RecallCaseSet(name=name, version=1, case_ids=tuple(case_ids), created=self._clock())
        missing = [cid for cid in wanted.case_ids if self.get_case(cid) is None]
        if missing:
            raise RecallStoreError(f"Case set '{name}' names unknown case ids: {missing}")
        while True:
            latest = self.get_case_set(name)
            if latest is not None and latest.case_ids == wanted.case_ids:
                return latest
            created = wanted.model_copy(update={"version": 1 if latest is None else latest.version + 1})
            envelope = _envelope(RECORD_TYPE_RECALL_CASE_SET, recall_case_set=created)
            try:
                self._store.create_record(created.record_id, envelope)
            except FileExistsError:
                # A concurrent writer took this version; re-read and compare against it.
                continue
            return created

    def get_case_set(self, name: str, version: int | None = None) -> RecallCaseSet | None:
        """The named set at *version*, the newest when ``None``; ``None`` when absent."""
        if version is not None:
            return self._load_set(name, version)
        latest: RecallCaseSet | None = None
        next_version = 1
        while (found := self._load_set(name, next_version)) is not None:
            latest = found
            next_version += 1
        return latest

    def resolve_set(self, ref: str) -> RecallCaseSet:
        """The set ``NAME[@VERSION]`` names; a missing set raises."""
        name, version = parse_set_ref(ref)
        found = self.get_case_set(name, version)
        if found is None:
            raise RecallStoreError(f"No recall case set {ref!r}")
        return found

    def list_case_sets(self) -> list[RecallCaseSet]:
        sets = [r.recall_case_set for r in self._iter(RECORD_TYPE_RECALL_CASE_SET) if r.recall_case_set]
        return sorted(sets, key=lambda item: (item.name, item.version))

    # ------------------------------------------------------------------- runs

    def get_run(self, case_id: str, run_index: int) -> RecallRun | None:
        record = self._load(run_record_id(case_id, run_index), RECORD_TYPE_RECALL_RUN)
        return None if record is None else record.recall_run

    def put_run(self, run: RecallRun) -> None:
        """Rewrite the run record in place; a failure is logged at ERROR and re-raised."""
        self._write(run.record_id, _envelope(RECORD_TYPE_RECALL_RUN, recall_run=run))

    def list_runs(self, case_ids: Iterable[str] | None = None) -> list[RecallRun]:
        """Run records of the given cases (every case when ``None``)."""
        wanted = None if case_ids is None else set(case_ids)
        runs = [
            r.recall_run
            for r in self._iter(RECORD_TYPE_RECALL_RUN)
            if r.recall_run and (wanted is None or r.recall_run.case_id in wanted)
        ]
        return sorted(runs, key=lambda run: (run.case_id, run.run_index))

    # ----------------------------------------------------------------- labels

    def get_labels(self, case_id: str, labeler: str) -> RecallLabels | None:
        record = self._load(labels_record_id(case_id, labeler), RECORD_TYPE_RECALL_LABELS)
        return None if record is None else record.recall_labels

    def put_labels(self, labels: RecallLabels) -> None:
        self._write(labels.record_id, _envelope(RECORD_TYPE_RECALL_LABELS, recall_labels=labels))

    def list_labels(self, case_ids: Iterable[str] | None = None) -> list[RecallLabels]:
        wanted = None if case_ids is None else set(case_ids)
        found = [
            r.recall_labels
            for r in self._iter(RECORD_TYPE_RECALL_LABELS)
            if r.recall_labels and (wanted is None or r.recall_labels.case_id in wanted)
        ]
        return sorted(found, key=lambda item: (item.case_id, item.labeler))

    def list_recipe_reviews(self) -> list[RecipeReview]:
        """Every ``recipe_review`` record (slice 434 D8), oldest first."""
        found = [r.recipe_review for r in self._iter(RECORD_TYPE_RECIPE_REVIEW) if r.recipe_review]
        return sorted(found, key=lambda record: record.created)

    # ---------------------------------------------------------------- helpers

    def _write(self, record_id: str, record: MetrologyRecord) -> None:
        try:
            self._store.write_record(record_id, record)
        except MetrologyStoreError:
            _logger.exception("Failed to write recall record %s", record_id)
            raise

    def _iter(self, record_type: str) -> Iterable[MetrologyRecord]:
        return (record for _, record in self._store.iter_records() if record.record_type == record_type)

    def _load_set(self, name: str, version: int) -> RecallCaseSet | None:
        record = self._load(case_set_id(name, version), RECORD_TYPE_RECALL_CASE_SET)
        return None if record is None else record.recall_case_set

    def _load(self, record_id: str, record_type: str) -> MetrologyRecord | None:
        """Absent is ``None``; unreadable or of another type raises."""
        try:
            record = self._store.load_record(record_id)
        except FileNotFoundError:
            return None
        except (ValueError, SchemaVersionError, OSError) as exc:
            _logger.exception("unreadable recall record %s", record_id)
            raise RecallStoreError(f"Unreadable recall record {record_id}: {exc}") from exc
        if record.record_type != record_type:
            _logger.error("record %s is %s, not %s", record_id, record.record_type, record_type)
            raise RecallStoreError(f"Record {record_id} is not a {record_type} record")
        return record


def _envelope(record_type: str, **payload: object) -> MetrologyRecord:
    return MetrologyRecord.model_validate(
        {"schema_version": _SCHEMA_VERSION, "record_type": record_type, **payload}
    )
