"""Store and back-compat tests for code snapshots (slice 400, D3 and Criterion 10)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import pytest

from squadron.metrology.errors import MetrologyStoreError
from squadron.metrology.levels import ArtifactLevel
from squadron.metrology.models import EvidenceSnapshot, GraduatedConfig, JudgeConfigId
from squadron.metrology.store import MetrologyStore, snapshot_record_id
from tests.metrology.conftest import (
    make_audit_run,
    make_noise_floor,
    make_sample_verdict,
)
from tests.metrology.replay_builders import make_judgment, make_replay
from tests.metrology.snapshot.builders import make_code_snapshot, make_project_id


class TestWriteAndList:
    def test_write_then_list_returns_the_snapshot(self, snapshot_store: MetrologyStore) -> None:
        snapshot = make_code_snapshot()

        record_id = snapshot_store.write_snapshot(snapshot)

        assert record_id == snapshot.snapshot_id
        assert snapshot_store.list_snapshots(make_project_id()) == [snapshot]

    def test_commit_filter_and_project_filter(self, snapshot_store: MetrologyStore) -> None:
        first = make_code_snapshot(commit_sha="a" * 40)
        second = make_code_snapshot(commit_sha="b" * 40)
        other_project = make_code_snapshot(project_value="github.com/manta/other")
        for snapshot in (first, second, other_project):
            snapshot_store.write_snapshot(snapshot)

        assert snapshot_store.list_snapshots(make_project_id(), "a" * 40) == [first]
        assert len(snapshot_store.list_snapshots(make_project_id())) == 2

    def test_newest_first(self, snapshot_store: MetrologyStore) -> None:
        older = make_code_snapshot(commit_sha="a" * 40, measured_at=datetime(2026, 1, 1, tzinfo=UTC))
        newer = make_code_snapshot(commit_sha="b" * 40, measured_at=datetime(2026, 2, 1, tzinfo=UTC))
        snapshot_store.write_snapshot(older)
        snapshot_store.write_snapshot(newer)

        listed = snapshot_store.list_snapshots(make_project_id())

        assert [snap.commit_sha for snap in listed] == ["b" * 40, "a" * 40]


class TestOverwrite:
    def test_second_write_leaves_one_record_and_logs_info(
        self, snapshot_store: MetrologyStore, caplog: pytest.LogCaptureFixture
    ) -> None:
        snapshot_store.write_snapshot(make_code_snapshot())

        with caplog.at_level(logging.INFO, logger="squadron.metrology.store"):
            snapshot_store.write_snapshot(
                make_code_snapshot(measured_at=datetime(2026, 11, 1, tzinfo=UTC))
            )

        assert len(list(snapshot_store.store_dir.glob("snapshot-*.json"))) == 1
        replaced = [r for r in caplog.records if "Replaced the earlier code snapshot" in r.message]
        assert len(replaced) == 1
        assert "c" * 40 in replaced[0].message

    def test_first_write_does_not_log_a_replacement(
        self, snapshot_store: MetrologyStore, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.INFO, logger="squadron.metrology.store"):
            snapshot_store.write_snapshot(make_code_snapshot())

        assert not [r for r in caplog.records if "Replaced" in r.message]

    def test_different_commits_get_different_ids(self) -> None:
        project = make_project_id()

        assert snapshot_record_id(project, "a" * 40) != snapshot_record_id(project, "b" * 40)
        assert snapshot_record_id(project, "a" * 40) != snapshot_record_id(
            make_project_id("github.com/manta/other"), "a" * 40
        )

    def test_snapshot_id_must_match_the_derived_record_id(self, snapshot_store: MetrologyStore) -> None:
        snapshot = make_code_snapshot().model_copy(update={"snapshot_id": "snapshot-wrong"})

        with pytest.raises(MetrologyStoreError, match="does not match"):
            snapshot_store.write_snapshot(snapshot)

        assert not list(snapshot_store.store_dir.glob("snapshot-*.json"))


class TestBackCompat:
    def test_every_existing_record_type_still_loads_beside_a_snapshot(
        self, snapshot_store: MetrologyStore
    ) -> None:
        sample = make_sample_verdict()
        graduated = GraduatedConfig(
            judge_config=JudgeConfigId(
                template_name="judge.slice-vs-arch",
                model="minimax/minimax-m2.7",
                template_content_hash="a" * 64,
            ),
            artifact_level=ArtifactLevel.SLICE_DESIGN_VS_ARCH,
            evidence=EvidenceSnapshot(n=10, match_rate=0.95, floor_applied=5, below_floor=False),
            graduated_at=datetime(2026, 7, 25, tzinfo=UTC),
        )
        run = make_audit_run()
        floor = make_noise_floor()
        replay = make_replay()
        judgment = make_judgment()

        snapshot_store.write_sample(sample)
        snapshot_store.write_graduation(graduated)
        snapshot_store.write_audit_run(run)
        snapshot_store.write_noise_floor(floor)
        snapshot_store.write_replay(replay)
        snapshot_store.write_judgment(judgment)
        snapshot_store.write_snapshot(make_code_snapshot())

        assert snapshot_store.list_samples() == [sample]
        assert [g for _, g in snapshot_store.list_graduations()] == [graduated]
        assert snapshot_store.list_audit_runs() == [run]
        assert [f for _, f in snapshot_store.list_noise_floors()] == [floor]
        assert len(snapshot_store.list_snapshots(make_project_id())) == 1
        assert len(list(snapshot_store.store_dir.glob("*.json"))) == 7
