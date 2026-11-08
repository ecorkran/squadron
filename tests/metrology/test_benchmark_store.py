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
from tests.metrology.test_benchmark_models import NOW, environment, qualification


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


class TestFixQualifications:
    @staticmethod
    def digest_of(env_lock: str = "l" * 64) -> str:
        return environment(env_lock).identity_digest

    def test_write_then_get_returns_equal_record(self, store: BenchmarkRecordStore) -> None:
        record = qualification()
        assert store.write_fix_qualification(record) == record.record_id
        found = store.get_fix_qualification(project(), record.commit_sha, self.digest_of())
        assert found == record

    def test_absent_key_is_none(self, store: BenchmarkRecordStore) -> None:
        assert store.get_fix_qualification(project(), "c" * 40, None) is None

    def test_second_write_under_same_key_keeps_one_file_with_later_result(
        self, store: BenchmarkRecordStore, tmp_path: Path
    ) -> None:
        store.write_fix_qualification(qualification(detail="first"))
        store.write_fix_qualification(qualification(detail="second"))
        assert len(list(tmp_path.glob("*.json"))) == 1
        found = store.get_fix_qualification(project(), "c" * 40, self.digest_of())
        assert found is not None
        assert found.detail == "second"

    def test_different_environment_digest_leaves_two_records(
        self, store: BenchmarkRecordStore, tmp_path: Path
    ) -> None:
        store.write_fix_qualification(qualification())
        store.write_fix_qualification(qualification(environment=environment("m" * 64)))
        assert len(list(tmp_path.glob("*.json"))) == 2
        assert store.get_fix_qualification(project(), "c" * 40, self.digest_of("m" * 64))

    def test_list_filters_by_project(self, store: BenchmarkRecordStore) -> None:
        mine = qualification()
        theirs = qualification(project_id=project("other"))
        store.write_fix_qualification(mine)
        store.write_fix_qualification(theirs)
        assert store.list_fix_qualifications(project()) == [mine]
        assert store.list_fix_qualifications(project("other")) == [theirs]
        assert len(store.list_fix_qualifications()) == 2

    def test_tampered_file_raises_on_get_and_warns_on_list(
        self,
        store: BenchmarkRecordStore,
        raw: MetrologyStore,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        record = qualification()
        store.write_fix_qualification(record)
        path = raw.record_location(record.record_id)
        data = json.loads(path.read_text(encoding="utf-8"))
        data["fix_qualification"]["outcome"] = "rejected"  # now disagrees with case_id
        path.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(MetrologyStoreError):
            store.get_fix_qualification(project(), record.commit_sha, self.digest_of())
        with caplog.at_level("WARNING"):
            assert store.list_fix_qualifications(project()) == []
        assert "Skipping unreadable metrology record" in caplog.text

    def test_wrong_type_record_raises_on_get(
        self, store: BenchmarkRecordStore, raw: MetrologyStore
    ) -> None:
        record = qualification()
        case = make_case()
        store.write_case(case)
        # A case envelope planted under the qualification's id is a foreign record.
        raw.write_record(record.record_id, raw.load_record(case.case_id))
        with pytest.raises(MetrologyStoreError, match="not a fix qualification"):
            store.get_fix_qualification(project(), record.commit_sha, self.digest_of())

    def test_record_written_before_this_change_still_loads(
        self, store: BenchmarkRecordStore, raw: MetrologyStore
    ) -> None:
        case = make_case()
        store.write_case(case)
        path = raw.record_location(case.case_id)
        data = json.loads(path.read_text(encoding="utf-8"))
        data.pop("fix_qualification")  # the envelope as 421 wrote it
        path.write_text(json.dumps(data), encoding="utf-8")
        assert store.get_case(case.case_id) == case


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
