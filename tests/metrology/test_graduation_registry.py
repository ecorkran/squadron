"""Tests for the graduated-config registry (T11/T12)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest

from squadron.metrology.graduation import find_graduation, list_graduations, write_graduation
from squadron.metrology.levels import ArtifactLevel
from squadron.metrology.models import EvidenceSnapshot, GraduatedConfig, JudgeConfigId
from squadron.metrology.store import MetrologyStore


def _judge_config(
    template_name: str = "judge.slice-vs-arch",
    model: str = "minimax/minimax-m2.7",
    template_content_hash: str | None = "a" * 64,
) -> JudgeConfigId:
    return JudgeConfigId(
        template_name=template_name, model=model, template_content_hash=template_content_hash
    )


def _evidence() -> EvidenceSnapshot:
    return EvidenceSnapshot(n=10, match_rate=0.95, floor_applied=5, below_floor=False)


def _graduated(
    judge_config: JudgeConfigId | None = None,
    artifact_level: ArtifactLevel = ArtifactLevel.SLICE_DESIGN_VS_ARCH,
) -> GraduatedConfig:
    return GraduatedConfig(
        judge_config=judge_config if judge_config is not None else _judge_config(),
        artifact_level=artifact_level,
        evidence=_evidence(),
        graduated_at=datetime(2026, 7, 25, tzinfo=UTC),
    )


class TestWriteAndFind:
    def test_write_then_find_round_trips(self, tmp_path: Path) -> None:
        store = MetrologyStore(store_dir=tmp_path)
        graduated = _graduated()
        write_graduation(store, graduated)

        found = find_graduation(store, graduated.judge_config, graduated.artifact_level)
        assert found == graduated

    def test_find_matches_identical_judge_config_id_and_level(self, tmp_path: Path) -> None:
        store = MetrologyStore(store_dir=tmp_path)
        graduated = _graduated()
        write_graduation(store, graduated)

        found = find_graduation(
            store,
            _judge_config(),  # a fresh but identical JudgeConfigId instance
            ArtifactLevel.SLICE_DESIGN_VS_ARCH,
        )
        assert found is not None
        assert found.judge_config == graduated.judge_config

    def test_find_returns_none_when_no_match(self, tmp_path: Path) -> None:
        store = MetrologyStore(store_dir=tmp_path)
        result = find_graduation(store, _judge_config(), ArtifactLevel.SLICE_DESIGN_VS_ARCH)
        assert result is None


class TestVersionScopedMatching:
    def test_differing_template_content_hash_does_not_match(self, tmp_path: Path) -> None:
        # Version-scoping regression (322 review F002): two JudgeConfigIds
        # sharing template_name+model but differing template_content_hash
        # must not cross-match — a graduation must not silently transfer
        # across a prompt/model edit.
        store = MetrologyStore(store_dir=tmp_path)
        graduated_under_hash1 = _graduated(judge_config=_judge_config(template_content_hash="hash-1"))
        write_graduation(store, graduated_under_hash1)

        found = find_graduation(
            store,
            _judge_config(template_content_hash="hash-2"),
            ArtifactLevel.SLICE_DESIGN_VS_ARCH,
        )
        assert found is None

    def test_differing_artifact_level_does_not_match(self, tmp_path: Path) -> None:
        store = MetrologyStore(store_dir=tmp_path)
        graduated = _graduated(artifact_level=ArtifactLevel.SLICE_DESIGN_VS_ARCH)
        write_graduation(store, graduated)

        found = find_graduation(store, graduated.judge_config, ArtifactLevel.TASKS_VS_SLICE)
        assert found is None


class TestListGraduations:
    def test_list_returns_all_written_records(self, tmp_path: Path) -> None:
        store = MetrologyStore(store_dir=tmp_path)
        write_graduation(store, _graduated(judge_config=_judge_config(model="model-a")))
        write_graduation(store, _graduated(judge_config=_judge_config(model="model-b")))

        result = list_graduations(store)
        assert len(result) == 2

    def test_list_tolerates_corrupt_sibling(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        store = MetrologyStore(store_dir=tmp_path)
        write_graduation(store, _graduated())

        corrupt = tmp_path / "graduation-corrupt.json"
        corrupt.write_text("{not valid json", encoding="utf-8")

        with caplog.at_level(logging.WARNING, logger="squadron.metrology.store"):
            result = list_graduations(store)

        assert len(result) == 1
        assert any(
            "graduation-corrupt.json" in record.message and record.levelno == logging.WARNING
            for record in caplog.records
        )

    def test_list_empty_store_returns_empty_list(self, tmp_path: Path) -> None:
        store = MetrologyStore(store_dir=tmp_path)
        assert list_graduations(store) == []


class TestIdempotentReGraduate:
    def test_re_graduate_same_identity_updates_in_place(self, tmp_path: Path) -> None:
        store = MetrologyStore(store_dir=tmp_path)
        first = _graduated()
        write_graduation(store, first)

        updated = first.model_copy(
            update={
                "evidence": EvidenceSnapshot(n=50, match_rate=0.98, floor_applied=5, below_floor=False)
            }
        )
        write_graduation(store, updated)

        all_graduations = list_graduations(store)
        assert len(all_graduations) == 1
        assert all_graduations[0].evidence.n == 50
