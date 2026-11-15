"""``ContentSidecars``: one write-once, hash-verified store per kind (slice 425 D11)."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import pytest

from squadron.metrology.benchmark_store import BenchmarkRecordStore
from squadron.metrology.content_sidecars import (
    SIDECAR_SUFFIXES,
    ContentSidecars,
    SidecarKind,
)
from squadron.metrology.errors import MetrologyStoreError
from squadron.metrology.store import MetrologyStore
from tests.metrology.test_benchmark_store import make_case

PAYLOAD = b'{"findings": []}'
ALL_KINDS = list(SidecarKind)


def _file(root: Path, kind: SidecarKind, data: bytes) -> Path:
    digest = hashlib.sha256(data).hexdigest()
    return root / "sidecars" / kind.value / f"{digest}{SIDECAR_SUFFIXES[kind]}"


@pytest.mark.parametrize("kind", ALL_KINDS)
def test_each_kind_round_trips_under_its_own_directory_and_suffix(
    tmp_path: Path, kind: SidecarKind
) -> None:
    sidecars = ContentSidecars(tmp_path, kind)
    digest = sidecars.put(PAYLOAD)
    assert digest == hashlib.sha256(PAYLOAD).hexdigest()
    assert sidecars.get(digest) == PAYLOAD
    assert _file(tmp_path, kind, PAYLOAD).is_file()


def test_suffixes_follow_the_design() -> None:
    assert SIDECAR_SUFFIXES[SidecarKind.DIFFS] == ".diff"
    assert {SIDECAR_SUFFIXES[kind] for kind in ALL_KINDS if kind is not SidecarKind.DIFFS} == {".json"}


def test_same_bytes_put_twice_write_once(tmp_path: Path) -> None:
    sidecars = ContentSidecars(tmp_path, SidecarKind.SNAPSHOTS)
    digest = sidecars.put(PAYLOAD)
    path = _file(tmp_path, SidecarKind.SNAPSHOTS, PAYLOAD)
    mtime = path.stat().st_mtime_ns
    assert sidecars.put(PAYLOAD) == digest
    assert path.stat().st_mtime_ns == mtime
    assert [p.name for p in path.parent.iterdir()] == [path.name]


@pytest.mark.parametrize("kind", ALL_KINDS)
def test_tampered_file_raises_on_get_and_on_second_put_and_logs_error(
    tmp_path: Path, kind: SidecarKind, caplog: pytest.LogCaptureFixture
) -> None:
    sidecars = ContentSidecars(tmp_path, kind)
    digest = sidecars.put(PAYLOAD)
    _file(tmp_path, kind, PAYLOAD).write_bytes(b"tampered")
    with caplog.at_level(logging.ERROR), pytest.raises(MetrologyStoreError, match="sha256"):
        sidecars.get(digest)
    assert any(
        r.levelno == logging.ERROR and "does not match" in r.getMessage() for r in caplog.records
    )
    with pytest.raises(MetrologyStoreError, match="sha256"):
        sidecars.put(PAYLOAD)


def test_a_missing_hash_raises_and_logs_error(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.ERROR), pytest.raises(MetrologyStoreError, match="missing"):
        ContentSidecars(tmp_path, SidecarKind.NODES).get("a" * 64)
    assert any(r.levelno == logging.ERROR for r in caplog.records)


def test_a_key_that_is_not_a_digest_raises(tmp_path: Path) -> None:
    with pytest.raises(MetrologyStoreError, match="not a sha256"):
        ContentSidecars(tmp_path, SidecarKind.REVIEWS).get("../../etc/passwd")


def test_kinds_do_not_share_a_directory(tmp_path: Path) -> None:
    for kind in ALL_KINDS:
        ContentSidecars(tmp_path, kind).put(PAYLOAD)
    directories = {_file(tmp_path, kind, PAYLOAD).parent for kind in ALL_KINDS}
    assert len(directories) == len(ALL_KINDS)
    other = ContentSidecars(tmp_path, SidecarKind.NODES)
    digest = hashlib.sha256(b"only in snapshots").hexdigest()
    ContentSidecars(tmp_path, SidecarKind.SNAPSHOTS).put(b"only in snapshots")
    with pytest.raises(MetrologyStoreError, match="missing"):
        other.get(digest)


def test_record_store_exposes_every_kind_and_keeps_the_diff_return_type(tmp_path: Path) -> None:
    store = BenchmarkRecordStore(MetrologyStore(store_dir=tmp_path))
    ref = store.diffs.put(b"diff --git a/x b/x\n")
    assert ref.files_changed == 1
    for sidecars, kind in (
        (store.snapshots, SidecarKind.SNAPSHOTS),
        (store.nodes, SidecarKind.NODES),
        (store.reviews, SidecarKind.REVIEWS),
    ):
        assert sidecars.get(sidecars.put(PAYLOAD)) == PAYLOAD
        assert _file(tmp_path, kind, PAYLOAD).is_file()


def test_sidecars_are_not_read_as_records(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    raw = MetrologyStore(store_dir=tmp_path)
    store = BenchmarkRecordStore(raw)
    case = make_case()
    store.write_case(case)
    for sidecars in (store.snapshots, store.nodes, store.reviews):
        sidecars.put(PAYLOAD)
    with caplog.at_level(logging.WARNING):
        records = list(raw.iter_records())
    assert [record_id for record_id, _ in records] == [case.case_id]
    assert caplog.records == []
