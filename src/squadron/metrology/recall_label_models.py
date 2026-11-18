"""Recall label records: known-bug hit labels and finding grades per (case, labeler) (D3, D5)."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

RECALL_LABELS_ID_PREFIX = "rblabels-"
_UNSAFE = re.compile(r"[^A-Za-z0-9_-]")
_LABELER_HASH_DIGITS = 8


class HitVerdict(StrEnum):
    HIT = "HIT"
    ADJACENT = "ADJACENT"
    MISS = "MISS"


class FindingGrade(StrEnum):
    """The grade words of the committed grading passes (D5)."""

    REAL = "REAL"
    MINOR = "MINOR"
    FALSE = "FALSE"
    PREEXISTING = "PREEXISTING"
    UNSURE = "UNSURE"


class LabelerKind(StrEnum):
    PERSON = "person"
    IMPORT = "import"


#: Labeler-name prefixes, one per kind: ``person:<name>`` and ``import:<brief>``.
LABELER_PREFIX: dict[LabelerKind, str] = {
    LabelerKind.PERSON: "person:",
    LabelerKind.IMPORT: "import:",
}


class RecallLabels(BaseModel):
    """One labeler's hit labels and grades for one case."""

    model_config = ConfigDict(frozen=True)

    case_id: str
    labeler: str
    labeler_kind: LabelerKind
    hits: dict[str, dict[str, HitVerdict]] = {}
    grades: dict[str, FindingGrade] = {}
    updated: datetime
    notes: str | None = None

    @property
    def record_id(self) -> str:
        return labels_record_id(self.case_id, self.labeler)


def labeler_name(kind: LabelerKind, name: str) -> str:
    """``person:<name>`` or ``import:<name>``."""
    return f"{LABELER_PREFIX[kind]}{name}"


def labels_record_id(case_id: str, labeler: str) -> str:
    """``rblabels-<case_id>-<labeler>-<sha8>``: the labeler reduced to path-safe characters,
    plus a hash of the exact name, so two labelers that reduce alike keep separate records."""
    digest = hashlib.sha256(labeler.encode("utf-8")).hexdigest()[:_LABELER_HASH_DIGITS]
    return f"{RECALL_LABELS_ID_PREFIX}{case_id}-{_UNSAFE.sub('_', labeler)}-{digest}"
