"""BenchmarkRecordStore: cases and versioned case sets (slice 421 D1-D3)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from squadron.metrology.benchmark_models import (
    BenchmarkCase,
    CaseKind,
    CaseProvenance,
    GraderCommand,
    GraderCommandKind,
    case_set_record_id,
)
from squadron.metrology.benchmark_store import BenchmarkRecordStore
from squadron.metrology.errors import MetrologyStoreError
from squadron.metrology.project_id import ProjectId, ProjectIdSource
from squadron.metrology.store import MetrologyStore
from tests.metrology.test_benchmark_models import NOW


def project(value: str = "proj") -> ProjectId:
    return ProjectId(value=value, source=ProjectIdSource.RECORDED)


def make_case(task: str = "fix", project_value: str = "proj") -> BenchmarkCase:
    return BenchmarkCase.build(
        project_id=project(project_value),
        kind=CaseKind.FIX,
        start_sha="a" * 40,
        reference_sha="b" * 40,
        task_text=task,
        hidden_tests=("t.py::x",),
        hidden_fixtures=(),
        superseded_tests=(),
        excluded_tests=(),
        grader_commands=(GraderCommand(kind=GraderCommandKind.SUITE, argv=("pytest",)),),
        provenance=CaseProvenance(source_ref="issue-1", created_at=NOW, built_by="test"),
    )


@pytest.fixture
def raw(tmp_path: Path) -> MetrologyStore:
    return MetrologyStore(store_dir=tmp_path)


@pytest.fixture
def store(raw: MetrologyStore) -> BenchmarkRecordStore:
    return BenchmarkRecordStore(raw)


class TestCases:
    def test_write_then_get_returns_equal_case(self, store: BenchmarkRecordStore) -> None:
        case = make_case()
        assert store.write_case(case) == case.case_id
        assert store.get_case(case.case_id) == case

    def test_writing_twice_leaves_one_file(self, store: BenchmarkRecordStore, tmp_path: Path) -> None:
        case = make_case()
        store.write_case(case)
        store.write_case(case)
        assert len(list(tmp_path.glob("*.json"))) == 1

    def test_unknown_id_is_none(self, store: BenchmarkRecordStore) -> None:
        assert store.get_case("case-0000000000000000") is None

    def test_case_set_record_passed_to_get_case_raises(self, store: BenchmarkRecordStore) -> None:
        case = make_case()
        store.write_case(case)
        case_set = store.write_case_set("everything", [case.case_id])
        with pytest.raises(MetrologyStoreError, match="not a benchmark case"):
            store.get_case(case_set.record_id)

    def test_tampered_file_raises_on_get_and_warns_on_list(
        self,
        store: BenchmarkRecordStore,
        raw: MetrologyStore,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        case = make_case()
        store.write_case(case)
        path = raw.record_location(case.case_id)
        data = json.loads(path.read_text(encoding="utf-8"))
        data["benchmark_case"]["task_text"] = "edited by hand"
        path.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(MetrologyStoreError):
            store.get_case(case.case_id)
        with caplog.at_level("WARNING"):
            assert store.list_cases(project()) == []
        assert "Skipping unreadable metrology record" in caplog.text

    def test_list_cases_filters_by_project(self, store: BenchmarkRecordStore) -> None:
        mine, theirs = make_case(), make_case(project_value="other")
        store.write_case(mine)
        store.write_case(theirs)
        assert store.list_cases(project()) == [mine]
        assert store.list_cases(project("other")) == [theirs]


class TestCaseSets:
    @pytest.fixture
    def ids(self, store: BenchmarkRecordStore) -> list[str]:
        return [store.write_case(make_case(task)) for task in ("one", "two", "three")]

    def test_first_write_is_v1(self, store: BenchmarkRecordStore, ids: list[str]) -> None:
        created = store.write_case_set("core", ids[:2])
        assert created.version == 1
        assert created.case_ids == tuple(sorted(ids[:2]))

    def test_same_list_in_any_order_returns_existing(
        self, store: BenchmarkRecordStore, ids: list[str]
    ) -> None:
        first = store.write_case_set("core", ids[:2])
        again = store.write_case_set("core", list(reversed(ids[:2])))
        assert again == first
        assert len(store.list_case_sets()) == 1

    def test_changed_list_creates_v2_and_leaves_v1(
        self, store: BenchmarkRecordStore, ids: list[str]
    ) -> None:
        first = store.write_case_set("core", ids[:2])
        second = store.write_case_set("core", ids)
        assert second.version == 2
        assert store.get_case_set("core", 1) == first

    def test_unknown_ids_rejected_naming_each(
        self, store: BenchmarkRecordStore, ids: list[str]
    ) -> None:
        with pytest.raises(MetrologyStoreError) as caught:
            store.write_case_set("core", [ids[0], "case-aaaa", "case-bbbb"])
        assert "case-aaaa" in str(caught.value)
        assert "case-bbbb" in str(caught.value)
        assert store.get_case_set("core") is None

    def test_get_latest_and_by_version(self, store: BenchmarkRecordStore, ids: list[str]) -> None:
        store.write_case_set("core", ids[:1])
        v2 = store.write_case_set("core", ids)
        assert store.get_case_set("core") == v2
        assert store.get_case_set("core", 1) is not None
        assert store.get_case_set("core", 3) is None
        assert store.get_case_set("absent") is None

    def test_list_orders_by_name_then_version_and_names_do_not_collide(
        self, store: BenchmarkRecordStore, ids: list[str]
    ) -> None:
        store.write_case_set("zeta", ids[:1])
        store.write_case_set("alpha", ids[:1])
        store.write_case_set("alpha", ids)
        listed = store.list_case_sets()
        assert [(s.name, s.version) for s in listed] == [("alpha", 1), ("alpha", 2), ("zeta", 1)]
        assert case_set_record_id("alpha", 1) != case_set_record_id("zeta", 1)


def test_concurrent_writers_never_overwrite_a_version(
    store: BenchmarkRecordStore, raw: MetrologyStore
) -> None:
    ids = [store.write_case(make_case(task)) for task in ("a", "b", "c", "d")]
    first = store.write_case_set("race", ids[:1])
    real_get = store.get_case_set
    calls = {"n": 0}

    def stale_then_real(name: str, version: int | None = None):  # type: ignore[no-untyped-def]
        # The first lookup misses the version a concurrent writer is about to create.
        calls["n"] += 1
        if calls["n"] == 1:
            return first
        return real_get(name, version)

    # A rival writes v2 between our read of v1 and our write.
    rival = BenchmarkRecordStore(raw)
    rival.write_case_set("race", ids[:2])
    store.get_case_set = stale_then_real  # type: ignore[method-assign]
    mine = store.write_case_set("race", ids[2:])
    assert mine.version == 3
    assert [s.version for s in store.list_case_sets()] == [1, 2, 3]
    assert rival.get_case_set("race", 2).case_ids == tuple(sorted(ids[:2]))  # type: ignore[union-attr]
