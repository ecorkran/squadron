"""Recall label models (slice 430 D3, D5)."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from squadron.metrology.recall_label_models import (
    FindingGrade,
    HitVerdict,
    LabelerKind,
    RecallLabels,
    labels_record_id,
)

RESULTS = Path(__file__).parents[3] / "project-documents/user/reference/review-recall-results"


def _grade_words() -> set[str]:
    words: set[str] = set()
    for path in RESULTS.glob("*/precision/*-graded*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        for section in ("issues", "new_issues"):
            words.update(issue["grade"] for issue in data.get(section, []))
    return words


def test_every_committed_grade_word_maps_to_a_member() -> None:
    words = _grade_words()
    assert words, "no graded files found"
    for word in words:
        assert FindingGrade(word).value == word


def test_label_id_path_safe() -> None:
    record_id = labels_record_id("rbcase-abc", "import:grid3/BRIEF-B2.md")
    assert re.fullmatch(r"[A-Za-z0-9_-]+", record_id)
    assert record_id.startswith("rblabels-rbcase-abc-")


def test_labelers_that_sanitize_alike_get_distinct_ids() -> None:
    assert labels_record_id("c", "person:a.b") != labels_record_id("c", "person:a_b")
    assert labels_record_id("c", "import:grid3/BRIEF.md") != labels_record_id(
        "c", "import:grid3_BRIEF_md"
    )


def test_round_trip_json() -> None:
    labels = RecallLabels(
        case_id="rbcase-abc",
        labeler="person:erik",
        labeler_kind=LabelerKind.PERSON,
        hits={"k1": {"B1": HitVerdict.HIT}},
        grades={"k1": FindingGrade.REAL},
        updated=datetime(2026, 11, 18, tzinfo=UTC),
    )
    assert RecallLabels.model_validate_json(labels.model_dump_json()) == labels
