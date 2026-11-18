"""Import part 3: grading passes, hit labels, overrides and label precedence (D3, D5, D10)."""

from __future__ import annotations

import json
import logging
import shutil
from datetime import timedelta
from pathlib import Path

import pytest

from squadron.benchmark.recall.hand_run_import import build_import_plan
from squadron.benchmark.recall.hand_run_labels import GRADING_PASSES
from squadron.benchmark.recall.hand_run_overrides import OVERRIDES_LABELER
from squadron.benchmark.recall.import_plan import ImportPlan
from squadron.benchmark.recall.label_precedence import resolve_labels
from squadron.metrology.recall_label_models import FindingGrade, HitVerdict, LabelerKind, RecallLabels
from tests.benchmark.recall.committed import OVERRIDES_FILE, RESULTS_DIR, committed_cases
from tests.benchmark.recall.support import FIXED_NOW

SET_LABEL = "real-bugs@v1"


@pytest.fixture(scope="module")
def real_plan() -> ImportPlan:
    return build_import_plan(RESULTS_DIR, committed_cases().values(), SET_LABEL, OVERRIDES_FILE)


def _labels_of(plan: ImportPlan, case_file: str) -> list[RecallLabels]:
    case_id = committed_cases()[case_file].case_id
    return [label for label in plan.labels.values() if label.case_id == case_id]


def test_four_import_labelers_present(real_plan: ImportPlan) -> None:
    labelers = {label.labeler for label in real_plan.labels.values()}
    assert {p.labeler for p in GRADING_PASSES} <= labelers
    assert len({p.labeler for p in GRADING_PASSES}) == 4
    assert not real_plan.skipped


def test_partial_cf5e840c_hit_is_imported_as_hit(real_plan: ImportPlan) -> None:
    resolved = resolve_labels(_labels_of(real_plan, "context-forge-5e840ccb.yaml"))
    assert any(bugs.get("B1") is HitVerdict.HIT for bugs in resolved.hits.values())


def test_overrides_land_under_person_labeler_and_win(real_plan: ImportPlan) -> None:
    for case_file, grade, imported in (
        ("trading-data-921.yaml", FindingGrade.REAL, FindingGrade.MINOR),
        ("squadron-197.yaml", FindingGrade.MINOR, None),
    ):
        records = _labels_of(real_plan, case_file)
        person = [r for r in records if r.labeler == OVERRIDES_LABELER]
        assert len(person) == 1 and person[0].labeler_kind is LabelerKind.PERSON
        resolved = resolve_labels(records)
        for key in person[0].grades:
            assert resolved.grades[key] is grade
            assert resolved.grade_labeler[key] == OVERRIDES_LABELER
            if imported is not None:
                assert resolved.import_grades[key] is imported


def _results_copy(tmp_path: Path) -> Path:
    """grid2 review files of case 175 plus its grid2 grade file, in a temp results folder."""
    root = tmp_path / "results"
    grid = root / "20261112-grid2"
    (grid / "precision").mkdir(parents=True)
    for path in (RESULTS_DIR / "20261112-grid2").glob("175-*.json"):
        shutil.copy(path, grid)
    shutil.copy(RESULTS_DIR / "20261112-grid2" / "precision" / "175-graded.json", grid / "precision")
    return root


def test_conflict_between_passes_is_listed_and_later_wins(tmp_path: Path) -> None:
    root = _results_copy(tmp_path)
    first = json.loads((root / "20261112-grid2" / "precision" / "175-graded.json").read_text())
    issue = first["issues"][0]
    ref, grade = issue["members"][0], issue["grade"]
    other = "FALSE" if grade != "FALSE" else "REAL"
    later = {
        "case": "175",
        "matched": {},
        "new_issues": [dict(issue, id="175-X1", grade=other, members=[ref])],
    }
    precision = root / "20261113-grid3" / "precision"
    precision.mkdir(parents=True)
    (precision / "175-graded.json").write_text(json.dumps(later), encoding="utf-8")
    plan = build_import_plan(root, committed_cases().values(), SET_LABEL)
    grade_conflicts = [c for c in plan.conflicts if c.what == "grade"]
    assert len(grade_conflicts) == 1
    assert grade_conflicts[0].winner == f"import:grid3/BRIEF.md={other}"
    resolved = resolve_labels(plan.labels.values())
    assert resolved.grades[grade_conflicts[0].content_key] == FindingGrade(other)


def test_bad_ref_and_unknown_override_issue_skipped_with_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    root = _results_copy(tmp_path)
    graded = root / "20261112-grid2" / "precision" / "175-graded.json"
    document = json.loads(graded.read_text())
    document["issues"][0]["members"].append("haiku-xhigh/9/0")
    graded.write_text(json.dumps(document), encoding="utf-8")
    overrides = tmp_path / "overrides.yaml"
    overrides.write_text(
        "- {case: squadron-175, issue: 175-I999, grade: REAL, reason: test}\n", encoding="utf-8"
    )
    with caplog.at_level(logging.WARNING):
        plan = build_import_plan(root, committed_cases().values(), SET_LABEL, overrides)
    items = [s.item for s in plan.skipped]
    assert any(item.endswith("haiku-xhigh/9/0") for item in items)
    assert any("175-I999" in item for item in items)
    assert (
        sum("import skipped" in r.getMessage() for r in caplog.records if r.levelno == logging.WARNING)
        == 2
    )


def _person(name: str, grade: FindingGrade, hit: HitVerdict, minutes: int) -> RecallLabels:
    return RecallLabels(
        case_id="rbcase-x",
        labeler=f"person:{name}",
        labeler_kind=LabelerKind.PERSON,
        hits={"k1": {"B1": hit}},
        grades={"k1": grade},
        updated=FIXED_NOW + timedelta(minutes=minutes),
    )


def test_newest_person_wins_and_person_beats_import() -> None:
    imported = RecallLabels(
        case_id="rbcase-x",
        labeler="import:grid2/BRIEF.md",
        labeler_kind=LabelerKind.IMPORT,
        hits={"k1": {"B1": HitVerdict.MISS}, "k2": {"B1": HitVerdict.HIT}},
        grades={"k1": FindingGrade.FALSE, "k2": FindingGrade.REAL},
        updated=FIXED_NOW + timedelta(days=9),
    )
    newer = _person("newer", FindingGrade.MINOR, HitVerdict.ADJACENT, 5)
    older = _person("older", FindingGrade.REAL, HitVerdict.HIT, 1)
    resolved = resolve_labels([newer, imported, older])
    assert resolved.hit("k1", "B1") is HitVerdict.ADJACENT
    assert resolved.grades["k1"] is FindingGrade.MINOR
    assert resolved.grade_labeler["k1"] == "person:newer"
    assert resolved.import_grades["k1"] is FindingGrade.FALSE
    assert resolved.hit("k2", "B1") is HitVerdict.HIT
