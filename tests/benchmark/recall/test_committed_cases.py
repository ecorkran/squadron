"""The committed real-bug case files and set lists (slice 430 D1, D13).

Locations are derived with a fake runner fed from ``fixtures/proof_files.json``, so no git
or source repo is needed.
"""

from __future__ import annotations

import pytest

from squadron.benchmark.recall.case_models import CaseFileSpec, derive_locations, load_case_file
from tests.benchmark.recall.committed import CASES_DIR, SETS_FILE, case_files, parse_sets, proof_runner

#: Set name -> (case count, bug count), from the design's Functional Requirements.
EXPECTED_SETS = {
    "real-bugs": (17, 21),
    "real-bugs-original": (10, 14),
    "real-bugs-original-no-u103": (9, 13),
    "real-bugs-nonsquadron": (14, 18),
}


@pytest.fixture(scope="module")
def specs() -> dict[str, CaseFileSpec]:
    return {path.name: load_case_file(path) for path in case_files()}


def test_seventeen_cases_twenty_one_bugs(specs: dict[str, CaseFileSpec]) -> None:
    assert len(specs) == 17
    assert sum(len(spec.bugs) for spec in specs.values()) == 21


def test_every_case_derives_locations_from_captured_proofs(specs: dict[str, CaseFileSpec]) -> None:
    runner = proof_runner()
    for name, spec in specs.items():
        bugs = derive_locations(CASES_DIR / name, spec, runner, timeout=1)
        assert all(bug.locations for bug in bugs), name


def test_hand_run_ids_are_unique(specs: dict[str, CaseFileSpec]) -> None:
    ids = [spec.hand_run_id for spec in specs.values()]
    assert None not in ids
    assert len(set(ids)) == len(ids)


def test_set_lists_resolve_with_stated_counts(specs: dict[str, CaseFileSpec]) -> None:
    sets = parse_sets(SETS_FILE.read_text(encoding="utf-8"))
    assert set(sets) == set(EXPECTED_SETS)
    for name, members in sets.items():
        assert len(set(members)) == len(members), name
        missing = [member for member in members if not (CASES_DIR / member).is_file()]
        assert not missing, f"{name}: {missing}"
        bug_count = sum(len(specs[member].bugs) for member in members)
        assert (len(members), bug_count) == EXPECTED_SETS[name], name
