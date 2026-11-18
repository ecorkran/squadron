"""Recall run model keys and round trip (slice 430 D4)."""

from __future__ import annotations

from datetime import UTC, datetime

from squadron.core.models import Effort
from squadron.metrology.benchmark_replay_enums import LeakVerdict
from squadron.metrology.recall_run_models import (
    UNKNOWN_MARKER,
    CombDecision,
    CombVerdict,
    RecallFinding,
    RecallLeakVerdict,
    RecallRun,
    StageConfig,
    StageEntry,
    StageKind,
    StageOutcome,
    chain_key,
    comb_slot,
    content_key,
    entry_key,
    parent_chain_key,
    run_record_id,
)

CONFIG = StageConfig(model="m", profile="p", template_hash="t", tool_use=None, max_output_tokens=None)


def test_config_key_ignores_alias_and_configured_effort() -> None:
    a = _entry(alias="a", effort=Effort.high)
    b = _entry(alias="b", effort=Effort.low)
    assert a.config.config_key == b.config.config_key
    assert a.entry_key != b.entry_key


def test_config_key_changes_with_fields() -> None:
    other = CONFIG.model_copy(update={"tool_use": UNKNOWN_MARKER})
    assert other.config_key != CONFIG.config_key
    assert CONFIG.model_copy(update={"max_output_tokens": 10}).config_key != CONFIG.config_key


def test_entry_key_includes_configured_effort() -> None:
    assert entry_key(CONFIG, Effort.high) != entry_key(CONFIG, None)
    assert entry_key(CONFIG, Effort.high) == entry_key(CONFIG, Effort.high)


def test_content_key_whitespace_insensitive() -> None:
    assert content_key("a.py:1", "T  x", "d\n e") == content_key(" a.py:1", "T x", "d e ")
    assert content_key("a.py:1", "T", "d") != content_key("a.py:2", "T", "d")


def test_chain_parent_is_chain_minus_last() -> None:
    chain = chain_key(["k1", "k2"])
    assert chain == "k1>k2"
    assert parent_chain_key(chain) == "k1"
    assert parent_chain_key("k1") is None
    assert comb_slot("e", chain) == "e|k1>k2"


def test_leak_values_come_from_424() -> None:
    assert RecallLeakVerdict.LEAKED.value == LeakVerdict.LEAKED.value
    assert RecallLeakVerdict.SCAN_UNAVAILABLE.value == LeakVerdict.SCAN_UNAVAILABLE.value


def test_run_record_id_deterministic() -> None:
    assert run_record_id("rbcase-x", 1) == run_record_id("rbcase-x", 1)
    assert run_record_id("rbcase-x", 1) != run_record_id("rbcase-x", 2)
    assert run_record_id("rbcase-x", 1).startswith("rbrun-")


def test_round_trip_json() -> None:
    review = _entry()
    comb = review.model_copy(
        update={
            "kind": StageKind.COMB,
            "findings": (),
            "decisions": {"f1": CombDecision(verdict=CombVerdict.KEEP, reason="r")},
        }
    )
    run = RecallRun(
        case_id="rbcase-x",
        run_index=1,
        reviews={review.entry_key: review},
        combs={comb_slot(review.entry_key, comb.entry_key): comb},
    )
    assert RecallRun.model_validate_json(run.model_dump_json()) == run
    unknown = CONFIG.model_copy(
        update={"tool_use": UNKNOWN_MARKER, "max_output_tokens": UNKNOWN_MARKER}
    )
    assert StageConfig.model_validate_json(unknown.model_dump_json()) == unknown


def _entry(alias: str = "a", effort: Effort | None = None) -> StageEntry:
    finding = RecallFinding(
        finding_id="f1",
        content_key=content_key("a.py", "t", "d"),
        severity="FAIL",
        category=None,
        location="a.py",
        title="t",
        description="d",
    )
    return StageEntry(
        kind=StageKind.REVIEW,
        config=CONFIG,
        effort_configured=effort,
        effort_sent=None,
        findings=(finding,),
        outcome=StageOutcome.OK,
        leak=RecallLeakVerdict.NOT_SCANNED,
        source="import:grid2",
        case_set="real-bugs@v1",
        alias=alias,
        created=datetime(2026, 11, 18, tzinfo=UTC),
    )
