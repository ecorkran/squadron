"""Tests for the metrology record models (T6/T7)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from squadron.metrology.models import (
    RECORD_TYPE_AUDIT_FINDING,
    RECORD_TYPE_SAMPLE,
    MetrologyRecord,
    SampleVerdict,
)
from squadron.review.models import Verdict
from tests.metrology.conftest import make_sample_verdict


class TestSampleVerdict:
    def test_round_trips_through_json_unchanged(self) -> None:
        sample = make_sample_verdict()
        record = MetrologyRecord(schema_version=1, sample=sample)
        restored = MetrologyRecord.model_validate_json(record.model_dump_json())
        assert restored == record
        assert restored.sample is not None
        assert isinstance(restored.sample.human_verdict, Verdict)

    def test_blind_defaults_true(self) -> None:
        assert make_sample_verdict().blind is True

    def test_invalid_human_verdict_rejected(self) -> None:
        sample = make_sample_verdict()
        payload = sample.model_dump()
        payload["human_verdict"] = "MAYBE"
        with pytest.raises(ValidationError):
            SampleVerdict.model_validate(payload)


class TestMetrologyRecordEnvelope:
    def test_sample_record_type_accepted(self) -> None:
        record = MetrologyRecord(schema_version=1, sample=make_sample_verdict())
        assert record.record_type == RECORD_TYPE_SAMPLE
        assert record.sample is not None

    def test_reserved_non_sample_type_validates_with_no_sample(self) -> None:
        # Reserves the 323 path: an audit_finding envelope with sample=None
        # validates today, so a second record type needs no migration.
        record = MetrologyRecord(
            schema_version=1,
            record_type=RECORD_TYPE_AUDIT_FINDING,
            sample=None,
        )
        restored = MetrologyRecord.model_validate_json(record.model_dump_json())
        assert restored.record_type == RECORD_TYPE_AUDIT_FINDING
        assert restored.sample is None
