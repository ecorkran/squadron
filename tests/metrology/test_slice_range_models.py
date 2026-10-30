"""The ``slice_ranges`` record models (slice 403, D1 and Storage Schema)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from squadron.metrology.levels import ArtifactLevel
from squadron.metrology.models import (
    RECORD_TYPE_AUDIT_FINDING,
    RECORD_TYPE_AUDIT_NOISE_FLOOR,
    RECORD_TYPE_CODE_REVIEW,
    RECORD_TYPE_CODE_SNAPSHOT,
    RECORD_TYPE_GRADUATED_CONFIG,
    RECORD_TYPE_PAIRWISE_JUDGMENT,
    RECORD_TYPE_PRODUCER_REPLAY,
    RECORD_TYPE_SAMPLE,
    RECORD_TYPE_SLICE_RANGES,
    EvidenceSnapshot,
    GraduatedConfig,
    JudgeConfigId,
    MetrologyRecord,
)
from squadron.metrology.slice_range_models import LandingMethod, SliceLanding, SliceRanges
from tests.metrology.conftest import make_audit_run, make_noise_floor, make_sample_verdict
from tests.metrology.replay_builders import make_judgment, make_replay
from tests.metrology.snapshot.builders import make_code_snapshot, make_project_id
from tests.metrology.test_review_models import make_record as make_review_record

RESOLVED_AT = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)


def make_landing(
    after_sha: str = "a" * 40,
    *,
    method: LandingMethod = LandingMethod.MERGE_COMMIT,
    merge_sha: str | None = "a" * 40,
) -> SliceLanding:
    return SliceLanding(
        method=method,
        target_ref="main",
        before_sha="b" * 40,
        after_sha=after_sha,
        fork_sha="c" * 40,
        tip_sha="d" * 40,
        merge_sha=merge_sha,
        resolved_at=RESOLVED_AT,
    )


def make_ranges(slices: dict[int, list[SliceLanding]]) -> SliceRanges:
    return SliceRanges(record_id="sliceranges-x", project_id=make_project_id(), slices=slices)


class TestValidation:
    def test_empty_landing_list_is_rejected_naming_the_slice(self) -> None:
        with pytest.raises(ValidationError, match=r"slice 403: landings must not be empty"):
            make_ranges({403: []})

    def test_duplicate_after_sha_is_rejected_naming_the_slice(self) -> None:
        landings = [make_landing("e" * 40), make_landing("e" * 40)]
        with pytest.raises(ValidationError, match=r"slice 403: duplicate after_sha"):
            make_ranges({403: landings})

    def test_merge_commit_without_merge_sha_is_rejected(self) -> None:
        landing = make_landing(method=LandingMethod.MERGE_COMMIT, merge_sha=None)
        with pytest.raises(ValidationError, match=r"slice 403: merge_sha is required"):
            make_ranges({403: [landing]})

    def test_fast_forward_with_merge_sha_is_rejected(self) -> None:
        landing = make_landing(method=LandingMethod.FAST_FORWARD, merge_sha="a" * 40)
        with pytest.raises(ValidationError, match=r"slice 403: merge_sha must be None"):
            make_ranges({403: [landing]})

    def test_fast_forward_without_merge_sha_is_valid(self) -> None:
        landing = make_landing(method=LandingMethod.FAST_FORWARD, merge_sha=None)
        assert make_ranges({403: [landing]}).slices[403] == [landing]


class TestRoundTrip:
    def test_two_landing_slice_round_trips_through_json(self) -> None:
        ranges = make_ranges({940: [make_landing("1" * 40), make_landing("2" * 40)]})
        record = MetrologyRecord(
            schema_version=1, record_type=RECORD_TYPE_SLICE_RANGES, slice_ranges=ranges
        )

        restored = MetrologyRecord.model_validate_json(record.model_dump_json())

        assert restored == record
        assert restored.slice_ranges is not None
        assert [x.after_sha for x in restored.slice_ranges.slices[940]] == ["1" * 40, "2" * 40]

    def test_slice_keys_survive_json_as_int(self) -> None:
        ranges = make_ranges({172: [make_landing()], 305: [make_landing()]})

        restored = SliceRanges.model_validate_json(ranges.model_dump_json())

        assert set(restored.slices) == {172, 305}
        assert all(isinstance(key, int) for key in restored.slices)


def _graduated_config() -> GraduatedConfig:
    return GraduatedConfig(
        judge_config=JudgeConfigId(
            template_name="judge.slice-vs-arch",
            model="minimax/minimax-m2.7",
            template_content_hash="a" * 64,
        ),
        artifact_level=ArtifactLevel.SLICE_DESIGN_VS_ARCH,
        evidence=EvidenceSnapshot(n=10, match_rate=0.95, floor_applied=5, below_floor=False),
        graduated_at=RESOLVED_AT,
    )


#: One envelope per record type that existed before 403, each with a real payload.
EXISTING_ENVELOPES: dict[str, MetrologyRecord] = {
    RECORD_TYPE_SAMPLE: MetrologyRecord(
        schema_version=1, record_type=RECORD_TYPE_SAMPLE, sample=make_sample_verdict()
    ),
    RECORD_TYPE_GRADUATED_CONFIG: MetrologyRecord(
        schema_version=1,
        record_type=RECORD_TYPE_GRADUATED_CONFIG,
        graduated_config=_graduated_config(),
    ),
    RECORD_TYPE_AUDIT_FINDING: MetrologyRecord(
        schema_version=1, record_type=RECORD_TYPE_AUDIT_FINDING, audit_run=make_audit_run()
    ),
    RECORD_TYPE_AUDIT_NOISE_FLOOR: MetrologyRecord(
        schema_version=1,
        record_type=RECORD_TYPE_AUDIT_NOISE_FLOOR,
        audit_noise_floor=make_noise_floor(),
    ),
    RECORD_TYPE_PRODUCER_REPLAY: MetrologyRecord(
        schema_version=1, record_type=RECORD_TYPE_PRODUCER_REPLAY, producer_replay=make_replay()
    ),
    RECORD_TYPE_PAIRWISE_JUDGMENT: MetrologyRecord(
        schema_version=1,
        record_type=RECORD_TYPE_PAIRWISE_JUDGMENT,
        pairwise_judgment=make_judgment(),
    ),
    RECORD_TYPE_CODE_SNAPSHOT: MetrologyRecord(
        schema_version=1, record_type=RECORD_TYPE_CODE_SNAPSHOT, code_snapshot=make_code_snapshot()
    ),
    RECORD_TYPE_CODE_REVIEW: MetrologyRecord(
        schema_version=1, record_type=RECORD_TYPE_CODE_REVIEW, code_review=make_review_record()
    ),
}


@pytest.mark.parametrize("record_type", sorted(EXISTING_ENVELOPES))
def test_existing_record_json_without_slice_ranges_key_loads_unchanged(record_type: str) -> None:
    on_disk = json.loads(EXISTING_ENVELOPES[record_type].model_dump_json())
    del on_disk["slice_ranges"]  # records written before 403 have no such key

    restored = MetrologyRecord.model_validate_json(json.dumps(on_disk))

    assert restored.slice_ranges is None
    assert restored.schema_version == 1
    assert restored == EXISTING_ENVELOPES[record_type]
