"""Benchmark runs, implementation replays and diff sidecars (slice 424 Task 15)."""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path

import pytest

from squadron.metrology.benchmark_replay_enums import BenchmarkStatus, ProducerOutcome
from squadron.metrology.benchmark_store import BenchmarkRecordStore, DiffSidecars
from squadron.metrology.errors import MetrologyStoreError
from squadron.metrology.store import MetrologyStore
from tests.metrology.test_benchmark_replay_models import _replay as make_replay
from tests.metrology.test_benchmark_replay_models import _run as make_run
from tests.metrology.test_benchmark_store import make_case

TWO_FILE_DIFF = (
    b"diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-a\n+b\n"
    b"diff --git a/y.py b/y.py\nnew file mode 100644\n"
)
requires_non_root = pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")


@pytest.fixture
def raw(tmp_path: Path) -> MetrologyStore:
    return MetrologyStore(store_dir=tmp_path)


@pytest.fixture
def store(raw: MetrologyStore) -> BenchmarkRecordStore:
    return BenchmarkRecordStore(raw)


def _sidecar_file(root: Path, data: bytes) -> Path:
    return root / "sidecars" / "diffs" / f"{hashlib.sha256(data).hexdigest()}.diff"


class TestDiffSidecars:
    def test_put_then_get_round_trips(self, tmp_path: Path) -> None:
        sidecars = DiffSidecars(tmp_path)
        ref = sidecars.put(TWO_FILE_DIFF)
        assert ref.sha256 == hashlib.sha256(TWO_FILE_DIFF).hexdigest()
        assert ref.bytes == len(TWO_FILE_DIFF)
        assert ref.files_changed == 2
        assert sidecars.get(ref.sha256) == TWO_FILE_DIFF

    def test_same_bytes_put_twice_write_once(self, tmp_path: Path) -> None:
        sidecars = DiffSidecars(tmp_path)
        first = sidecars.put(TWO_FILE_DIFF)
        path = _sidecar_file(tmp_path, TWO_FILE_DIFF)
        mtime = path.stat().st_mtime_ns
        assert sidecars.put(TWO_FILE_DIFF) == first
        assert path.stat().st_mtime_ns == mtime
        assert [p.name for p in path.parent.iterdir()] == [path.name]

    def test_empty_diff_is_valid(self, tmp_path: Path) -> None:
        sidecars = DiffSidecars(tmp_path)
        ref = sidecars.put(b"")
        assert (ref.bytes, ref.files_changed) == (0, 0)
        assert sidecars.get(ref.sha256) == b""

    def test_tampered_sidecar_fails_get_and_second_put(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        sidecars = DiffSidecars(tmp_path)
        ref = sidecars.put(TWO_FILE_DIFF)
        _sidecar_file(tmp_path, TWO_FILE_DIFF).write_bytes(b"tampered")
        with caplog.at_level(logging.ERROR), pytest.raises(MetrologyStoreError, match="sha256"):
            sidecars.get(ref.sha256)
        assert "does not match" in caplog.text
        with pytest.raises(MetrologyStoreError, match="sha256"):
            sidecars.put(TWO_FILE_DIFF)

    def test_missing_file_raises_and_logs_error(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.ERROR), pytest.raises(MetrologyStoreError, match="missing"):
            DiffSidecars(tmp_path).get("a" * 64)
        assert any(r.levelno == logging.ERROR for r in caplog.records)

    def test_key_that_is_not_a_digest_raises(self, tmp_path: Path) -> None:
        with pytest.raises(MetrologyStoreError, match="not a sha256"):
            DiffSidecars(tmp_path).get("../../etc/passwd")

    @requires_non_root
    def test_write_failure_raises_and_logs_error(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        tmp_path.chmod(0o500)
        try:
            with caplog.at_level(logging.ERROR), pytest.raises(MetrologyStoreError):
                DiffSidecars(tmp_path).put(TWO_FILE_DIFF)
        finally:
            tmp_path.chmod(0o700)
        assert any(r.levelno == logging.ERROR for r in caplog.records)


class TestRuns:
    def test_write_then_get_round_trips(self, store: BenchmarkRecordStore) -> None:
        run = make_run()
        assert store.write_run(run) == run.benchmark_id
        assert store.get_run(run.benchmark_id) == run
        assert store.list_runs() == [run]

    def test_overwrite_changes_status(self, store: BenchmarkRecordStore) -> None:
        run = make_run()
        store.write_run(run)
        done = run.model_copy(update={"status": BenchmarkStatus.COMPLETE})
        store.write_run(done)
        stored = store.get_run(run.benchmark_id)
        assert stored is not None
        assert stored.status == BenchmarkStatus.COMPLETE
        assert len(store.list_runs()) == 1

    def test_unknown_run_is_none(self, store: BenchmarkRecordStore) -> None:
        assert store.get_run("bench-0000000000000000") is None

    def test_case_record_passed_to_get_run_raises(self, store: BenchmarkRecordStore) -> None:
        case_id = store.write_case(make_case())
        with pytest.raises(MetrologyStoreError, match="not a benchmark run"):
            store.get_run(case_id)


class TestReplays:
    def test_write_then_get_round_trips(self, store: BenchmarkRecordStore) -> None:
        replay = make_replay()
        assert store.write_replay("implreplay-a", replay) == "implreplay-a"
        assert store.get_replay("implreplay-a") == replay

    def test_same_content_again_is_a_no_op(self, store: BenchmarkRecordStore) -> None:
        store.write_replay("implreplay-a", make_replay())
        store.write_replay("implreplay-a", make_replay())
        assert len(store.replays_for(make_replay().benchmark_id)) == 1

    def test_different_content_under_one_id_raises(
        self, store: BenchmarkRecordStore, caplog: pytest.LogCaptureFixture
    ) -> None:
        store.write_replay("implreplay-a", make_replay())
        other = make_replay().model_copy(update={"outcome": ProducerOutcome.NO_COMMIT})
        with caplog.at_level(logging.ERROR), pytest.raises(MetrologyStoreError, match="differs"):
            store.write_replay("implreplay-a", other)
        assert "different content" in caplog.text

    def test_replays_listed_per_benchmark(self, store: BenchmarkRecordStore) -> None:
        mine = make_replay()
        theirs = mine.model_copy(update={"benchmark_id": "bench-ffffffffffffffff"})
        store.write_replay("implreplay-b", mine)
        store.write_replay("implreplay-a", mine.model_copy(update={"sample": 1}))
        store.write_replay("implreplay-c", theirs)
        found = store.replays_for(mine.benchmark_id)
        assert [record_id for record_id, _ in found] == ["implreplay-a", "implreplay-b"]

    def test_delete_removes_only_named_ids_and_counts_them(self, store: BenchmarkRecordStore) -> None:
        replay = make_replay()
        for record_id in ("implreplay-a", "implreplay-b", "implreplay-c"):
            store.write_replay(record_id, replay)
        removed = store.delete_replays(["implreplay-a", "implreplay-c", "implreplay-missing"])
        assert removed == 2
        assert [rid for rid, _ in store.replays_for(replay.benchmark_id)] == ["implreplay-b"]

    def test_the_storage_layer_deletes_a_record_and_says_whether_it_existed(
        self, store: BenchmarkRecordStore, raw: MetrologyStore
    ) -> None:
        store.write_replay("implreplay-a", make_replay())
        assert raw.delete_record("implreplay-a") is True
        assert raw.delete_record("implreplay-a") is False
        assert store.get_replay("implreplay-a") is None

    def test_delete_refuses_a_record_that_is_not_a_replay(self, store: BenchmarkRecordStore) -> None:
        run_id = store.write_run(make_run())
        with pytest.raises(MetrologyStoreError, match="not an implementation replay"):
            store.delete_replays([run_id])
        assert store.get_run(run_id) is not None

    def test_delete_keeps_the_diff_sidecar(self, store: BenchmarkRecordStore, tmp_path: Path) -> None:
        ref = store.diffs.put(TWO_FILE_DIFF)
        store.write_replay("implreplay-a", make_replay().model_copy(update={"diff": ref}))
        store.delete_replays(["implreplay-a"])
        assert store.diffs.get(ref.sha256) == TWO_FILE_DIFF


class TestStoreLayout:
    def test_sidecar_never_appears_in_iter_records(
        self, store: BenchmarkRecordStore, raw: MetrologyStore, tmp_path: Path
    ) -> None:
        store.diffs.put(TWO_FILE_DIFF)
        store.write_run(make_run())
        assert [record_id for record_id, _ in raw.iter_records()] == [make_run().benchmark_id]
        assert not list(tmp_path.glob("*.diff"))

    @requires_non_root
    def test_failed_record_write_raises_and_logs_error(
        self, store: BenchmarkRecordStore, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        tmp_path.chmod(0o500)
        try:
            with caplog.at_level(logging.ERROR), pytest.raises(MetrologyStoreError):
                store.write_run(make_run())
        finally:
            tmp_path.chmod(0o700)
        assert "Failed to write benchmark record" in caplog.text
