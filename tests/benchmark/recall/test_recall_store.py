"""RecallRecordStore round trips and versioning (slice 430 D4)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from squadron.benchmark.recall.recall_store import RecallRecordStore, parse_set_ref
from squadron.metrology.errors import MetrologyStoreError
from squadron.metrology.recall_case_models import RealBugCase
from squadron.metrology.recall_label_models import HitVerdict, LabelerKind, RecallLabels
from squadron.metrology.recall_run_models import RecallRun
from squadron.metrology.store import MetrologyStore
from tests.benchmark.recall.support import case_fields

NOW = datetime(2026, 11, 18, tzinfo=UTC)


@pytest.fixture
def store(tmp_path: Path) -> RecallRecordStore:
    return RecallRecordStore(MetrologyStore(tmp_path / "store"), clock=lambda: NOW)


def _case(name: str, head: str) -> RealBugCase:
    return RealBugCase.build(**case_fields(name=name, head=head))


def test_case_round_trip_and_write_once(store: RecallRecordStore) -> None:
    case = _case("a", "1" * 40)
    assert store.write_case(case) is True
    assert store.write_case(case) is False
    assert store.get_case(case.case_id) == case
    assert store.list_cases() == [case]


def test_case_set_versions(store: RecallRecordStore) -> None:
    one, two = _case("a", "1" * 40), _case("b", "2" * 40)
    store.write_case(one)
    store.write_case(two)
    v1 = store.write_case_set("s", [one.case_id])
    assert v1.version == 1
    assert store.write_case_set("s", [one.case_id]).version == 1
    v2 = store.write_case_set("s", [one.case_id, two.case_id])
    assert v2.version == 2
    assert store.get_case_set("s") == v2
    assert store.resolve_set("s@1") == v1
    assert store.resolve_set("s@v2") == v2
    assert [s.version for s in store.list_case_sets()] == [1, 2]


def test_case_set_unknown_case_refused(store: RecallRecordStore) -> None:
    with pytest.raises(MetrologyStoreError, match="unknown case ids"):
        store.write_case_set("s", ["rbcase-missing"])


def test_parse_set_ref() -> None:
    assert parse_set_ref("real-bugs") == ("real-bugs", None)
    assert parse_set_ref("real-bugs@3") == ("real-bugs", 3)
    with pytest.raises(ValueError):
        parse_set_ref("a@b@c")


def test_run_rewrite_keeps_one_record(store: RecallRecordStore, tmp_path: Path) -> None:
    run = RecallRun(case_id="rbcase-x", run_index=1)
    store.put_run(run)
    store.put_run(run.model_copy(update={"run_index": 1, "superseded": []}))
    assert store.get_run("rbcase-x", 1) == run
    assert store.list_runs(["rbcase-x"]) == [run]
    assert store.list_runs(["rbcase-y"]) == []
    assert len(list((tmp_path / "store").glob("rbrun-*.json"))) == 1


def test_labels_round_trip(store: RecallRecordStore) -> None:
    labels = RecallLabels(
        case_id="rbcase-x",
        labeler="import:grid3/BRIEF-B2.md",
        labeler_kind=LabelerKind.IMPORT,
        hits={"k": {"B1": HitVerdict.HIT}},
        updated=NOW,
    )
    store.put_labels(labels)
    assert store.get_labels("rbcase-x", "import:grid3/BRIEF-B2.md") == labels
    assert store.list_labels(["rbcase-x"]) == [labels]


def test_write_failure_surfaces(store: RecallRecordStore, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*_args: object) -> None:
        raise MetrologyStoreError("disk full")

    monkeypatch.setattr(MetrologyStore, "write_record", fail)
    with pytest.raises(MetrologyStoreError, match="disk full"):
        store.put_run(RecallRun(case_id="rbcase-x", run_index=1))


def test_foreign_record_type_raises(store: RecallRecordStore) -> None:
    store.put_run(RecallRun(case_id="rbcase-x", run_index=1))
    run_id = RecallRun(case_id="rbcase-x", run_index=1).record_id
    with pytest.raises(MetrologyStoreError, match="not a recall_case"):
        store.get_case(run_id)
