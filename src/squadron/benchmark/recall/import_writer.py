"""Write an import plan to the recall store, changing only what differs (D10).

Imported entries merge into any stored run record, so live entries a later ``run`` added
are kept. A record is rewritten only when its content changes, which makes a second
import of the same folder write nothing.
"""

from __future__ import annotations

from dataclasses import dataclass

from squadron.benchmark.recall.import_plan import ImportPlan
from squadron.benchmark.recall.recall_store import RecallRecordStore
from squadron.metrology.recall_run_models import RecallRun


@dataclass(frozen=True)
class ImportWrite:
    runs_written: int
    labels_written: int

    @property
    def changed(self) -> bool:
        return bool(self.runs_written or self.labels_written)


def write_import_plan(store: RecallRecordStore, plan: ImportPlan) -> ImportWrite:
    """Put raw outputs in the sidecar, then every run and label record that changed."""
    for data in plan.raw_outputs.values():
        store.reviews.put(data)
    runs_written = 0
    for planned in plan.runs.values():
        stored = store.get_run(planned.case_id, planned.run_index)
        merged = _merge(stored, planned)
        if merged != stored:
            store.put_run(merged)
            runs_written += 1
    labels_written = 0
    for labels in plan.labels.values():
        if store.get_labels(labels.case_id, labels.labeler) != labels:
            store.put_labels(labels)
            labels_written += 1
    return ImportWrite(runs_written=runs_written, labels_written=labels_written)


def _merge(stored: RecallRun | None, planned: RecallRun) -> RecallRun:
    if stored is None:
        return planned
    return stored.model_copy(
        update={
            "reviews": {**stored.reviews, **planned.reviews},
            "combs": {**stored.combs, **planned.combs},
        }
    )
