"""The import plan: every record the hand-run import would write, and what it skipped (D10).

The plan builders fill it; nothing here touches the store. ``sq benchmark recall import``
prints its counts and, without ``--dry-run``, writes it.
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime

from squadron.metrology.recall_case_models import RealBugCase
from squadron.metrology.recall_label_models import RecallLabels
from squadron.metrology.recall_run_models import UNKNOWN_MARKER, RecallRun, StageConfig

_logger = logging.getLogger(__name__)
_FOLDER_DATE_DIGITS = 8


@dataclass(frozen=True)
class Skipped:
    """One file or ref left out, with the reason; listed in the import summary."""

    item: str
    reason: str


@dataclass(frozen=True)
class LabelConflict:
    """Two assignments gave one finding different values; ``winner`` (the later pass) was kept.

    ``what`` is ``grade`` or ``hit <bug id>``; ``loser``/``winner`` are ``<labeler>=<value>``.
    """

    case: str
    content_key: str
    what: str
    loser: str
    winner: str


@dataclass(frozen=True)
class ImportContext:
    """What every builder needs: the cases by hand-run id and the set label for entries."""

    cases_by_hand_id: dict[str, RealBugCase]
    case_set: str


@dataclass
class ImportPlan:
    runs: dict[str, RecallRun] = field(default_factory=dict[str, RecallRun])
    #: Raw output bytes by sha256, for the ``REVIEWS`` sidecar.
    raw_outputs: dict[str, bytes] = field(default_factory=dict[str, bytes])
    labels: dict[str, RecallLabels] = field(default_factory=dict[str, RecallLabels])
    skipped: list[Skipped] = field(default_factory=list[Skipped])
    duplicates: list[str] = field(default_factory=list[str])
    unknown_counts: Counter[str] = field(default_factory=Counter[str])
    conflicts: list[LabelConflict] = field(default_factory=list[LabelConflict])

    @property
    def review_entries(self) -> int:
        return sum(len(run.reviews) for run in self.runs.values())

    @property
    def comb_entries(self) -> int:
        return sum(len(run.combs) for run in self.runs.values())

    def skip(self, item: str, reason: str) -> None:
        """List *item* as skipped and log the WARNING D8 asks for."""
        _logger.warning("import skipped %s: %s", item, reason)
        self.skipped.append(Skipped(item, reason))

    def count_unknowns(self, config: StageConfig) -> None:
        """Count each identity field the source did not record (the D10 unknown markers)."""
        for name, value in config.model_dump().items():
            if value == UNKNOWN_MARKER or (
                isinstance(value, str) and value.startswith(f"{UNKNOWN_MARKER}:")
            ):
                self.unknown_counts[name] += 1


def folder_date(folder: str) -> datetime:
    """The ``YYYYMMDD`` a hand-run folder name starts with, as UTC midnight.

    Imported entries and labels take this as ``created``/``updated`` so that a second
    import builds byte-identical records.
    """
    return datetime.strptime(folder[:_FOLDER_DATE_DIGITS], "%Y%m%d").replace(tzinfo=UTC)
