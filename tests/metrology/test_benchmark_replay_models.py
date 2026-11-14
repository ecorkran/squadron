"""Tests for the implementation-replay and benchmark-run records (slice 424 Task 14)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from pydantic import BaseModel, ValidationError

from squadron.metrology.benchmark_environment import EnvironmentIdentity
from squadron.metrology.benchmark_models import CandidateRejection
from squadron.metrology.benchmark_replay_enums import (
    AbsenceClass,
    BenchmarkStatus,
    LeakRule,
    LeakVerdict,
    ProducerOutcome,
)
from squadron.metrology.benchmark_replay_models import (
    MAX_LEAK_EXCERPT_CHARS,
    MAX_LEAK_HITS,
    BenchmarkRun,
    CaseDrop,
    DiffRef,
    ImplementationReplay,
    LeakHit,
    LeakScanResult,
)
from squadron.metrology.models import (
    RECORD_TYPE_BENCHMARK_RUN,
    RECORD_TYPE_IMPLEMENTATION_REPLAY,
    MetrologyRecord,
)
from squadron.metrology.replay_models import ProducerConfigRef, PromptIdentity
from squadron.metrology.snapshot_models import SourceLanguage
from tests.metrology.conftest import make_sample_verdict

NOW = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)
MAX_REPLAY_RECORD_BYTES = 8 * 1024
INSTRUCTION_FILE_COUNT = 6


def _config() -> ProducerConfigRef:
    return ProducerConfigRef(
        alias="opus",
        model="claude-opus-5-5",
        profile="sdk",
        effort_sent="high",
        tool_use=True,
        max_output_tokens=None,
    )


def _environment() -> EnvironmentIdentity:
    return EnvironmentIdentity(
        language=SourceLanguage.PYTHON,
        lockfile_path="uv.lock",
        lockfile_sha256="a" * 64,
        interpreter_version="3.12.1",
        installer_version="uv 0.5",
        platform="darwin-arm64",
        scrub_spec_version=1,
    )


def _prompt() -> PromptIdentity:
    return PromptIdentity(
        sha256="b" * 64,
        source="pipeline:fix",
        squadron_version="0.24.28",
        cf_version="0.19.24",
        guide_version=None,
    )


def _clean_leak() -> LeakScanResult:
    return LeakScanResult(
        verdict=LeakVerdict.NO_LEAK_DETECTED,
        rules_version=1,
        tool_calls_seen=12,
        hits=(),
        detail="",
    )


def _replay() -> ImplementationReplay:
    return ImplementationReplay(
        benchmark_id="bench-0123456789abcdef",
        case_id="case-0123456789abcdef",
        case_set="fixes",
        case_set_version=1,
        sample=0,
        config=_config(),
        pipeline="fix",
        producer_step="fix",
        run_id="implreplay-0123456789ab-0123456789ab-01234567-s0",
        outcome=ProducerOutcome.COMMITTED,
        absence=None,
        failure_detail=None,
        leak=_clean_leak(),
        diff=DiffRef(sha256="c" * 64, bytes=2048, files_changed=3),
        commit_sha="d" * 40,
        environment=_environment(),
        prompt=_prompt(),
        instruction_files=tuple(
            (f".claude/rules/rule-{n}.md", f"{n:064x}") for n in range(INSTRUCTION_FILE_COUNT)
        ),
        cost_usd=0.42,
        turns=14,
        wall_seconds=181.5,
        squadron_version="0.24.28",
        created_at=NOW,
    )


def _run() -> BenchmarkRun:
    return BenchmarkRun(
        benchmark_id="bench-0123456789abcdef",
        case_set="fixes",
        case_set_version=1,
        configs=(_config(),),
        samples=3,
        status=BenchmarkStatus.PARTIAL,
        run_cap_usd=40.0,
        per_replay_cap_usd=1.5,
        spent_usd=12.25,
        unpriced_replays=1,
        case_drops=(
            CaseDrop(
                case_id="case-aaaaaaaaaaaaaaaa",
                reason=CandidateRejection.ENVIRONMENT_UNRESOLVED,
                environment_digest="e" * 64,
            ),
            CaseDrop(
                case_id="case-bbbbbbbbbbbbbbbb",
                reason="harness detail text",
                environment_digest="f" * 64,
            ),
        ),
        started_at=NOW,
        updated_at=NOW,
    )


def _leak_hit(index: int = 0, excerpt: str = "cat /home/user/x") -> LeakHit:
    return LeakHit(rule=LeakRule.PATH, tool=f"Bash{index}", excerpt=excerpt)


def _round_trip(model: BaseModel) -> BaseModel:
    return type(model).model_validate_json(model.model_dump_json())


class TestRoundTrip:
    @pytest.mark.parametrize(
        "model",
        [
            _leak_hit(),
            _clean_leak(),
            LeakScanResult(
                verdict=LeakVerdict.LEAKED,
                rules_version=1,
                tool_calls_seen=3,
                hits=(_leak_hit(),),
                detail="",
            ),
            DiffRef(sha256="c" * 64, bytes=0, files_changed=0),
            CaseDrop(
                case_id="case-aaaaaaaaaaaaaaaa",
                reason=CandidateRejection.NO_TEST_CHANGE,
                environment_digest="e" * 64,
            ),
            _replay(),
            _run(),
        ],
        ids=lambda model: type(model).__name__,
    )
    def test_model_round_trips_through_json(self, model: BaseModel) -> None:
        assert _round_trip(model) == model

    def test_replay_with_no_producer_run_round_trips(self) -> None:
        replay = _replay().model_copy(
            update={
                "outcome": ProducerOutcome.ENVIRONMENT_FAILED,
                "absence": AbsenceClass.HARNESS,
                "failure_detail": "sandbox failed",
                "leak": None,
                "diff": None,
                "commit_sha": None,
                "environment": None,
                "prompt": None,
                "cost_usd": None,
                "turns": None,
            }
        )
        assert _round_trip(replay) == replay

    def test_case_drop_reason_keeps_rejection_value(self) -> None:
        restored = _round_trip(_run())
        assert isinstance(restored, BenchmarkRun)
        assert restored.case_drops[0].reason == CandidateRejection.ENVIRONMENT_UNRESOLVED
        assert restored.case_drops[1].reason == "harness detail text"


class TestBounds:
    def test_twenty_hits_accepted(self) -> None:
        hits = tuple(_leak_hit(n) for n in range(MAX_LEAK_HITS))
        result = LeakScanResult(
            verdict=LeakVerdict.LEAKED, rules_version=1, tool_calls_seen=30, hits=hits, detail=""
        )
        assert len(result.hits) == MAX_LEAK_HITS

    def test_twenty_one_hits_raise(self) -> None:
        hits = tuple(_leak_hit(n) for n in range(MAX_LEAK_HITS + 1))
        with pytest.raises(ValidationError, match="limit is 20"):
            LeakScanResult(
                verdict=LeakVerdict.LEAKED,
                rules_version=1,
                tool_calls_seen=30,
                hits=hits,
                detail="",
            )

    def test_excerpt_of_limit_accepted(self) -> None:
        hit = _leak_hit(excerpt="x" * MAX_LEAK_EXCERPT_CHARS)
        assert len(hit.excerpt) == MAX_LEAK_EXCERPT_CHARS

    def test_excerpt_over_limit_raises_not_truncates(self) -> None:
        with pytest.raises(ValidationError, match="limit is 300"):
            _leak_hit(excerpt="x" * (MAX_LEAK_EXCERPT_CHARS + 1))

    def test_stored_oversized_excerpt_fails_on_read(self) -> None:
        payload = json.loads(_leak_hit().model_dump_json())
        payload["excerpt"] = "x" * 301
        with pytest.raises(ValidationError):
            LeakHit.model_validate(payload)


class TestEnums:
    def test_producer_outcome_values_equal_the_d10_table(self) -> None:
        assert [outcome.value for outcome in ProducerOutcome] == [
            "environment_failed",
            "no_run_state",
            "frozen_text_mismatch",
            "cost_cap",
            "blocked",
            "committed",
            "no_commit",
            "producer_failed",
        ]

    def test_absence_class_has_no_none_value(self) -> None:
        assert {member.value for member in AbsenceClass} == {"harness", "config"}

    def test_leak_verdict_rule_and_status_values(self) -> None:
        assert {member.value for member in LeakVerdict} == {
            "leaked",
            "no_leak_detected",
            "scan_unavailable",
        }
        assert {member.value for member in LeakRule} == {"path", "git_or_host", "own_package"}
        assert {member.value for member in BenchmarkStatus} == {
            "running",
            "complete",
            "partial",
            "interrupted",
        }


class TestEnvelope:
    def test_replay_payload_round_trips_in_the_envelope(self) -> None:
        record = MetrologyRecord(
            schema_version=1,
            record_type=RECORD_TYPE_IMPLEMENTATION_REPLAY,
            implementation_replay=_replay(),
        )
        restored = MetrologyRecord.model_validate_json(record.model_dump_json())
        assert restored == record

    def test_run_payload_round_trips_in_the_envelope(self) -> None:
        record = MetrologyRecord(
            schema_version=1, record_type=RECORD_TYPE_BENCHMARK_RUN, benchmark_run=_run()
        )
        restored = MetrologyRecord.model_validate_json(record.model_dump_json())
        assert restored == record

    def test_stored_320_record_without_the_new_fields_loads(self) -> None:
        stored = json.loads(
            MetrologyRecord(schema_version=1, sample=make_sample_verdict()).model_dump_json()
        )
        del stored["benchmark_run"]
        del stored["implementation_replay"]
        restored = MetrologyRecord.model_validate_json(json.dumps(stored))
        assert restored.sample is not None
        assert restored.benchmark_run is None
        assert restored.implementation_replay is None


class TestRecordSize:
    def test_representative_replay_serializes_under_8_kb(self) -> None:
        record = MetrologyRecord(
            schema_version=1,
            record_type=RECORD_TYPE_IMPLEMENTATION_REPLAY,
            implementation_replay=_replay(),
        )
        assert len(record.model_dump_json().encode()) < MAX_REPLAY_RECORD_BYTES
