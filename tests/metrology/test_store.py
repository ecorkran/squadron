"""Tests for the metrology store (T8/T9), modeled on tests/pipeline/test_state.py.

Covers round-trip, atomic-write failure with no partial record, schema-version
rejection, cross-project query, and judge-config filtering.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from squadron.metrology.errors import MetrologyStoreError
from squadron.metrology.models import RECORD_TYPE_SAMPLE, JudgeConfigId, MetrologyRecord
from squadron.metrology.store import MetrologyStore, SchemaVersionError
from tests.metrology.conftest import make_sample_verdict


class TestRoundTrip:
    def test_write_then_list_returns_record(self, tmp_path: Path) -> None:
        store = MetrologyStore(store_dir=tmp_path)
        sample = make_sample_verdict(sample_id="sample-20260722-aaaa1111")
        returned = store.write_sample(sample)
        assert returned == "sample-20260722-aaaa1111"
        listed = store.list_samples()
        assert len(listed) == 1
        assert listed[0].sample_id == sample.sample_id
        assert listed[0].human_verdict == sample.human_verdict

    def test_record_file_named_by_sample_id(self, tmp_path: Path) -> None:
        store = MetrologyStore(store_dir=tmp_path)
        sample = make_sample_verdict(sample_id="sample-20260722-bbbb2222")
        store.write_sample(sample)
        assert (tmp_path / "sample-20260722-bbbb2222.json").is_file()


class TestAtomicWrite:
    def test_rename_failure_raises_and_leaves_no_partial(self, tmp_path: Path) -> None:
        store = MetrologyStore(store_dir=tmp_path)
        sample = make_sample_verdict(sample_id="sample-20260722-cccc3333")
        # Simulate a rename failure mid-publish.
        with patch.object(Path, "replace", side_effect=OSError("disk full")):
            with pytest.raises(MetrologyStoreError):
                store.write_sample(sample)
        final = tmp_path / "sample-20260722-cccc3333.json"
        assert not final.exists()  # no partial record at the final path


class TestSchemaVersion:
    def test_unsupported_version_rejected_on_load(self, tmp_path: Path) -> None:
        store = MetrologyStore(store_dir=tmp_path)
        sample = make_sample_verdict(sample_id="sample-20260722-dddd4444")
        store.write_sample(sample)
        # Rewrite the file with a bad version.
        path = tmp_path / "sample-20260722-dddd4444.json"
        raw = json.loads(path.read_text())
        raw["schema_version"] = 999
        path.write_text(json.dumps(raw))
        with pytest.raises(SchemaVersionError):
            store.load_record("sample-20260722-dddd4444")

    def test_unsupported_version_skipped_in_list(self, tmp_path: Path) -> None:
        # A corrupt sibling must not sink the whole query.
        store = MetrologyStore(store_dir=tmp_path)
        good = make_sample_verdict(sample_id="sample-20260722-eeee5555")
        store.write_sample(good)
        bad_path = tmp_path / "sample-20260722-ffff6666.json"
        bad_path.write_text(json.dumps({"schema_version": 999, "record_type": "sample"}))
        listed = store.list_samples()
        assert [s.sample_id for s in listed] == ["sample-20260722-eeee5555"]


class TestQuery:
    def test_cross_project_query_returns_both(self, tmp_path: Path) -> None:
        store = MetrologyStore(store_dir=tmp_path)
        store.write_sample(
            make_sample_verdict(
                sample_id="sample-20260722-1111aaaa", project_value="github.com/o/proj-a"
            )
        )
        store.write_sample(
            make_sample_verdict(
                sample_id="sample-20260722-2222bbbb", project_value="github.com/o/proj-b"
            )
        )
        all_samples = store.list_samples()
        projects = {s.project_id.value for s in all_samples}
        assert projects == {"github.com/o/proj-a", "github.com/o/proj-b"}

    def test_project_filter_narrows(self, tmp_path: Path) -> None:
        store = MetrologyStore(store_dir=tmp_path)
        store.write_sample(
            make_sample_verdict(
                sample_id="sample-20260722-1111aaaa", project_value="github.com/o/proj-a"
            )
        )
        store.write_sample(
            make_sample_verdict(
                sample_id="sample-20260722-2222bbbb", project_value="github.com/o/proj-b"
            )
        )
        only_a = store.list_samples(project_id="github.com/o/proj-a")
        assert [s.sample_id for s in only_a] == ["sample-20260722-1111aaaa"]

    def test_judge_config_filter_narrows(self, tmp_path: Path) -> None:
        store = MetrologyStore(store_dir=tmp_path)
        store.write_sample(
            make_sample_verdict(
                sample_id="sample-20260722-1111aaaa", template_name="judge.slice-vs-arch"
            )
        )
        store.write_sample(
            make_sample_verdict(sample_id="sample-20260722-2222bbbb", template_name="judge.code")
        )
        target = JudgeConfigId(template_name="judge.code", model="minimax/minimax-m2.7")
        narrowed = store.list_samples(judge_config=target)
        assert [s.sample_id for s in narrowed] == ["sample-20260722-2222bbbb"]

    def test_template_model_filter_matches_despite_stored_hash(self, tmp_path: Path) -> None:
        # F003 regression: a template+model filter (hash None) must still match
        # a stored record that carries a populated template_content_hash — the
        # hash is a 322 version refinement, not part of a template+model query.
        store = MetrologyStore(store_dir=tmp_path)
        sample = make_sample_verdict(sample_id="sample-20260722-3333cccc")
        sample.judge_config.template_content_hash = "deadbeef" * 8
        store.write_sample(sample)
        wanted = JudgeConfigId(
            template_name=sample.judge_config.template_name,
            model=sample.judge_config.model,
        )
        assert wanted.template_content_hash is None
        matched = store.list_samples(judge_config=wanted)
        assert [s.sample_id for s in matched] == ["sample-20260722-3333cccc"]

    def test_filter_with_explicit_hash_still_narrows(self, tmp_path: Path) -> None:
        # When the filter *does* specify a hash, it narrows on it.
        store = MetrologyStore(store_dir=tmp_path)
        a = make_sample_verdict(sample_id="sample-20260722-aaaa0001")
        a.judge_config.template_content_hash = "aaaa" * 16
        b = make_sample_verdict(sample_id="sample-20260722-bbbb0002")
        b.judge_config.template_content_hash = "bbbb" * 16
        store.write_sample(a)
        store.write_sample(b)
        wanted = JudgeConfigId(
            template_name=a.judge_config.template_name,
            model=a.judge_config.model,
            template_content_hash="aaaa" * 16,
        )
        matched = store.list_samples(judge_config=wanted)
        assert [s.sample_id for s in matched] == ["sample-20260722-aaaa0001"]

    def test_count_samples_per_project(self, tmp_path: Path) -> None:
        store = MetrologyStore(store_dir=tmp_path)
        for i in range(3):
            store.write_sample(
                make_sample_verdict(
                    sample_id=f"sample-20260722-000{i}aaaa",
                    project_value="github.com/o/proj-a",
                )
            )
        store.write_sample(
            make_sample_verdict(
                sample_id="sample-20260722-9999bbbb", project_value="github.com/o/proj-b"
            )
        )
        assert store.count_samples("github.com/o/proj-a") == 3
        assert store.count_samples("github.com/o/proj-b") == 1


class TestPublicRecordPrimitives:
    """write_record / iter_records, the primitives benchmark records build on (421 D3)."""

    @staticmethod
    def _envelope() -> MetrologyRecord:
        return MetrologyRecord(
            schema_version=1,
            record_type=RECORD_TYPE_SAMPLE,
            sample=make_sample_verdict(sample_id="sample-20260722-cccc3333"),
        )

    def test_write_record_then_load_record_round_trips(self, tmp_path: Path) -> None:
        store = MetrologyStore(store_dir=tmp_path)
        record = self._envelope()
        store.write_record("sample-20260722-cccc3333", record)
        assert store.load_record("sample-20260722-cccc3333") == record

    def test_iter_records_skips_corrupt_file_with_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        store = MetrologyStore(store_dir=tmp_path)
        store.write_record("sample-20260722-cccc3333", self._envelope())
        (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")
        with caplog.at_level("WARNING"):
            ids = [record_id for record_id, _ in store.iter_records()]
        assert ids == ["sample-20260722-cccc3333"]
        assert "Skipping unreadable metrology record" in caplog.text

    def test_record_written_before_benchmark_fields_still_loads(self, tmp_path: Path) -> None:
        store = MetrologyStore(store_dir=tmp_path)
        data = self._envelope().model_dump(mode="json")
        del data["benchmark_case"], data["case_set"]
        (tmp_path / "old.json").write_text(json.dumps(data), encoding="utf-8")
        loaded = store.load_record("old")
        assert loaded.benchmark_case is None
        assert loaded.case_set is None
