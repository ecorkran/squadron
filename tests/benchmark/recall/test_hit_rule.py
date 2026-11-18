"""The hit rule: location gate and label resolution (slice 430 D3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.benchmark.recall.hit_rule import (
    GateResult,
    HitOutcome,
    cited_paths,
    gate,
    path_matches,
    resolve,
)
from squadron.benchmark.recall.label_precedence import resolve_labels
from squadron.metrology.recall_label_models import HitVerdict, LabelerKind, RecallLabels
from squadron.metrology.recall_run_models import RecallFinding, content_key
from tests.benchmark.recall.committed import imported_services
from tests.benchmark.recall.support import FIXED_NOW, make_bug


def _finding(location: str | None, description: str = "plain words") -> RecallFinding:
    return RecallFinding(
        finding_id="F1",
        content_key=content_key(location, "t", description),
        severity="CONCERN",
        category=None,
        location=location,
        title="t",
        description=description,
    )


@pytest.mark.parametrize(
    ("location", "expected"),
    [
        ("src/pkg/minute.py:12-30", ["src/pkg/minute.py"]),
        ("src/pkg/minute.py#Bar.load", ["src/pkg/minute.py"]),
        ("src/pkg/minute.py (the loader)", ["src/pkg/minute.py"]),
        ("minute.py", ["minute.py"]),
        ("`./web/app.tsx:4`", ["web/app.tsx"]),
        ("self.client and parts[0].metadata", []),
        (None, []),
    ],
)
def test_cited_path_forms(location: str | None, expected: list[str]) -> None:
    assert cited_paths(_finding(location)) == expected


def test_paths_are_read_from_the_description_too() -> None:
    finding = _finding(None, "calls `load()` in src/a.py and then b.py:9 (wrong); version 0.24.28")
    assert cited_paths(finding) == ["src/a.py", "b.py"]


def test_path_matches_at_slash_boundary_only() -> None:
    assert path_matches("minute.py", "src/x/minute.py")
    assert path_matches("src/x/minute.py", "x/minute.py")
    assert not path_matches("ute.py", "src/x/minute.py")


def test_gate_no_path_is_candidate_mismatch_is_decided_miss() -> None:
    bug = make_bug("B1", "src/a.py")
    assert gate(_finding(None), bug) is GateResult.CANDIDATE
    assert gate(_finding("src/a.py:3"), bug) is GateResult.CANDIDATE
    assert gate(_finding("src/other.py:3"), bug) is GateResult.DECIDED_MISS


def _labels(key: str, verdict: HitVerdict, kind: LabelerKind, name: str) -> RecallLabels:
    return RecallLabels(
        case_id="c",
        labeler=f"{kind.value}:{name}",
        labeler_kind=kind,
        hits={key: {"B1": verdict}},
        updated=FIXED_NOW,
    )


def test_resolve_uses_label_precedence_and_undecided() -> None:
    bug = make_bug("B1", "src/a.py")
    finding = _finding("src/a.py:3")
    assert resolve(finding, bug, resolve_labels([])) is HitOutcome.UNDECIDED
    imported = _labels(finding.content_key, HitVerdict.MISS, LabelerKind.IMPORT, "grid2/BRIEF.md")
    person = _labels(finding.content_key, HitVerdict.HIT, LabelerKind.PERSON, "pm")
    assert resolve(finding, bug, resolve_labels([imported])) is HitOutcome.MISS
    assert resolve(finding, bug, resolve_labels([imported, person])) is HitOutcome.HIT
    # The gate decides before any label: a decided miss stays a miss.
    elsewhere = _finding("src/other.py")
    hit_elsewhere = _labels(elsewhere.content_key, HitVerdict.HIT, LabelerKind.PERSON, "pm")
    assert resolve(elsewhere, bug, resolve_labels([hit_elsewhere])) is HitOutcome.MISS


def test_every_imported_hit_label_passes_the_gate(tmp_path: Path) -> None:
    store = imported_services(tmp_path).store
    failures: list[str] = []
    checked = 0
    for case in store.list_cases():
        findings = {
            finding.content_key: finding
            for run in store.list_runs([case.case_id])
            for entry in run.reviews.values()
            for finding in entry.findings
        }
        bugs = {bug.id: bug for bug in case.bugs}
        for labels in store.list_labels([case.case_id]):
            for key, by_bug in labels.hits.items():
                for bug_id, verdict in by_bug.items():
                    if verdict is not HitVerdict.HIT:
                        continue
                    checked += 1
                    finding = findings[key]
                    if gate(finding, bugs[bug_id]) is not GateResult.CANDIDATE:
                        failures.append(
                            f"{case.name} {bug_id} {finding.location} {cited_paths(finding)}"
                        )
    assert checked == 86
    assert not failures, "\n".join(failures)
