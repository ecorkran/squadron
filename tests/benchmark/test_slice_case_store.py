"""Slice-case record ids and store methods (slice 426, Task 12)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from squadron.metrology.benchmark_models import QualificationOutcome
from squadron.metrology.benchmark_store import BenchmarkRecordStore
from squadron.metrology.errors import MetrologyStoreError
from squadron.metrology.models import MetrologyRecord
from squadron.metrology.project_id import ProjectId, ProjectIdSource
from squadron.metrology.slice_case_models import (
    SliceCandidateRejection,
    diff_judgment_id,
    over_size_case_id,
    slice_qualification_id,
)
from squadron.metrology.slice_case_store import SliceCaseRecordStore
from squadron.metrology.store import MetrologyStore
from tests.benchmark.slice_case_support import (
    BENCHMARK_ID,
    CASE_ID,
    LANDING,
    PROJECT,
    environment,
    judge_ref,
    judgment,
    over_size,
    qualification,
)


@pytest.fixture
def metrology(tmp_path: Path) -> MetrologyStore:
    return MetrologyStore(store_dir=tmp_path / "store")


@pytest.fixture
def store(metrology: MetrologyStore) -> SliceCaseRecordStore:
    return SliceCaseRecordStore(BenchmarkRecordStore(metrology))


def test_pair_id_is_stable_across_ref_order_and_changes_with_judge() -> None:
    judge = judge_ref()
    forward = diff_judgment_id(BENCHMARK_ID, CASE_ID, ("x", "y"), judge)

    assert forward == diff_judgment_id(BENCHMARK_ID, CASE_ID, ("y", "x"), judge)
    assert forward != diff_judgment_id(
        BENCHMARK_ID, CASE_ID, ("x", "y"), judge_ref(prompt_hash="0" * 64)
    )
    assert forward != diff_judgment_id(BENCHMARK_ID, CASE_ID, ("x", "y"), judge_ref(alias="other"))
    assert forward.startswith("diffjudge-3f9c0a1b2c3d-0123456789ab-")


def test_over_size_id_changes_with_judge_prompt_and_alias() -> None:
    base = over_size_case_id(BENCHMARK_ID, CASE_ID, judge_ref())

    assert base != over_size_case_id(BENCHMARK_ID, CASE_ID, judge_ref(alias="other"))
    assert base != over_size_case_id(BENCHMARK_ID, CASE_ID, judge_ref(prompt_hash="0" * 64))
    assert base.startswith("oversize-3f9c0a1b2c3d-0123456789ab-")


def test_qualification_id_distinguishes_pre_sandbox_from_a_digest() -> None:
    digest = environment().identity_digest

    pre = slice_qualification_id(PROJECT, 403, LANDING, None)
    keyed = slice_qualification_id(PROJECT, 403, LANDING, digest)

    assert pre.endswith("-403-" + LANDING[:12] + "-pre")
    assert keyed.endswith(digest[:12])
    assert pre != keyed
    other_project = ProjectId(value="github.com/manta/other", source=ProjectIdSource.REMOTE)
    assert slice_qualification_id(other_project, 403, LANDING, None) != pre


def test_qualification_round_trips_and_a_newer_one_overwrites(store: SliceCaseRecordStore) -> None:
    older = qualification(start_environment=environment())
    store.write_slice_qualification(older)
    newer = qualification(
        QualificationOutcome.REJECTED,
        rejection=SliceCandidateRejection.NO_REGRESSION_SIGNAL,
        start_environment=environment(),
    )

    store.write_slice_qualification(newer)

    found = store.get_slice_qualification(PROJECT, 403, LANDING, environment().identity_digest)
    assert found == newer
    assert store.list_slice_qualifications() == [newer]


def test_the_pre_sandbox_record_is_addressed_by_none(store: SliceCaseRecordStore) -> None:
    pre = qualification(QualificationOutcome.REJECTED, rejection=SliceCandidateRejection.NO_CODE_CHANGE)
    store.write_slice_qualification(pre)

    assert store.get_slice_qualification(PROJECT, 403, LANDING, None) == pre
    assert store.get_slice_qualification(PROJECT, 403, LANDING, "9" * 64) is None


def test_listing_filters_by_project(store: SliceCaseRecordStore) -> None:
    store.write_slice_qualification(qualification())
    other = ProjectId(value="github.com/manta/other", source=ProjectIdSource.REMOTE)

    assert len(store.list_slice_qualifications(PROJECT)) == 1
    assert store.list_slice_qualifications(other) == []


def test_diff_judgments_round_trip_and_filter_by_alias(store: SliceCaseRecordStore) -> None:
    mine = judgment()
    theirs = judgment(judge=judge_ref(alias="other-judge"))
    store.write_diff_judgment(mine)
    store.write_diff_judgment(theirs)

    assert store.diff_judgments_for(BENCHMARK_ID) == sorted(
        [mine, theirs], key=lambda item: item.record_id
    )
    assert store.diff_judgments_for(BENCHMARK_ID, "gpt-judge") == [mine]
    assert store.diff_judgments_for("bench-someotherbenchmark") == []


def test_diff_judgments_by_alias_span_every_benchmark(store: SliceCaseRecordStore) -> None:
    here = judgment()
    elsewhere = judgment().model_copy(update={"benchmark_id": "bench-someotherbenchmark"})
    other_judge = judgment(judge=judge_ref(alias="other-judge"))
    for item in (here, elsewhere, other_judge):
        store.write_diff_judgment(item)

    found = store.diff_judgments_by("gpt-judge")

    assert found == sorted([here, elsewhere], key=lambda item: item.record_id)


def test_an_over_size_record_is_replaced_when_written_again_under_the_same_id(
    store: SliceCaseRecordStore,
) -> None:
    store.write_over_size_case(over_size(limit=1000))
    store.write_over_size_case(over_size(limit=2000))

    found = store.over_size_cases_for(BENCHMARK_ID)
    assert [record.max_prompt_chars for record in found] == [2000]
    assert store.over_size_cases_for(BENCHMARK_ID, "another-alias") == []


def test_a_store_file_written_without_the_new_payloads_still_loads(
    metrology: MetrologyStore, store: SliceCaseRecordStore
) -> None:
    metrology.write_record("fixqual-old", MetrologyRecord(schema_version=1, record_type="sample"))
    path = metrology.record_location("fixqual-old")

    envelope = json.loads(path.read_text())
    envelope.pop("slice_qualification", None)
    envelope.pop("diff_judgment", None)
    envelope.pop("over_size_case", None)
    path.write_text(json.dumps(envelope))

    assert metrology.load_record("fixqual-old").slice_qualification is None
    assert store.list_slice_qualifications() == []
    assert store.diff_judgments_for(BENCHMARK_ID) == []


def test_a_foreign_record_under_a_slice_id_raises(
    metrology: MetrologyStore, store: SliceCaseRecordStore
) -> None:
    record_id = slice_qualification_id(PROJECT, 403, LANDING, None)
    metrology.write_record(record_id, MetrologyRecord(schema_version=1, record_type="sample"))

    with pytest.raises(MetrologyStoreError, match="not a slice qualification"):
        store.get_slice_qualification(PROJECT, 403, LANDING, None)


def test_a_failing_write_raises_and_logs_error(
    metrology: MetrologyStore,
    store: SliceCaseRecordStore,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def refuse(record_id: str, record: MetrologyRecord) -> None:
        raise MetrologyStoreError("disk full")

    monkeypatch.setattr(metrology, "write_record", refuse)

    with caplog.at_level(logging.ERROR), pytest.raises(MetrologyStoreError, match="disk full"):
        store.write_diff_judgment(judgment())

    assert any(
        record.levelno == logging.ERROR and "diffjudge-" in record.getMessage()
        for record in caplog.records
    )
