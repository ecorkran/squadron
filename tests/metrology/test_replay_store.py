"""Producer-replay and pairwise-judgment records in the metrology store (slice 177 D9).

The judge filter is the comparability guard: a judgment made under a different
judge prompt is a different instrument and must not be pooled with this one.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

import pytest

from squadron.metrology.models import RECORD_TYPE_AUDIT_FINDING, MetrologyRecord
from squadron.metrology.replay_models import ReplayOutcome, ReplayPhase
from squadron.metrology.store import MetrologyStore, generate_judgment_id, generate_replay_id
from tests.metrology.conftest import make_audit_run
from tests.metrology.replay_builders import PROJECT, make_judge, make_judgment, make_replay


def test_generated_ids_have_the_documented_shape() -> None:
    for generated, prefix in ((generate_replay_id(), "replay"), (generate_judgment_id(), "pair")):
        head, stamp, suffix = generated.split("-")
        assert head == prefix
        assert len(stamp) == 8 and stamp.isdigit()
        assert len(suffix) == 8


def test_replay_round_trips_through_the_store(audit_store: MetrologyStore) -> None:
    replay = make_replay()

    record_id = audit_store.write_replay(replay)

    assert record_id.startswith("replay-")
    assert audit_store.list_replays(PROJECT) == [(record_id, replay)]


def test_judgment_round_trips_with_usage_records(audit_store: MetrologyStore) -> None:
    judgment = make_judgment()

    audit_store.write_judgment(judgment)

    (listed,) = audit_store.list_judgments(PROJECT)
    assert listed == judgment
    assert listed.first_usage is not None and listed.first_usage.cost_usd == 0.05


def test_list_replays_filters_by_project_phase_and_set(audit_store: MetrologyStore) -> None:
    keep = audit_store.write_replay(make_replay())
    audit_store.write_replay(make_replay(project_value="github.com/manta/other"))
    audit_store.write_replay(make_replay(phase=ReplayPhase.TASKS))
    audit_store.write_replay(make_replay(replay_set="set-2"))

    assert len(audit_store.list_replays(PROJECT)) == 3
    assert len(audit_store.list_replays(PROJECT, phase=ReplayPhase.DESIGN)) == 2
    only = audit_store.list_replays(PROJECT, phase=ReplayPhase.DESIGN, replay_set="set-1")
    assert [rid for rid, _ in only] == [keep]


def test_list_replays_is_newest_first(audit_store: MetrologyStore) -> None:
    older = audit_store.write_replay(make_replay(created_at=datetime(2026, 10, 1, tzinfo=UTC)))
    newer = audit_store.write_replay(make_replay(created_at=datetime(2026, 11, 1, tzinfo=UTC)))

    assert [rid for rid, _ in audit_store.list_replays(PROJECT)] == [newer, older]


def test_list_judgments_filters_by_project_and_phase(audit_store: MetrologyStore) -> None:
    audit_store.write_judgment(make_judgment())
    audit_store.write_judgment(make_judgment(project_value="github.com/manta/other"))
    audit_store.write_judgment(make_judgment(phase=ReplayPhase.TASKS))

    assert len(audit_store.list_judgments(PROJECT)) == 2
    assert len(audit_store.list_judgments(PROJECT, phase=ReplayPhase.TASKS)) == 1


def test_a_different_judge_prompt_hash_is_excluded(audit_store: MetrologyStore) -> None:
    audit_store.write_judgment(make_judgment(judge=make_judge("d" * 64)))
    audit_store.write_judgment(make_judgment(judge=make_judge("e" * 64)))

    matched = audit_store.list_judgments(PROJECT, judge=make_judge("d" * 64))

    assert [j.judge.prompt_hash for j in matched] == ["d" * 64]


def test_replay_and_judgment_do_not_leak_into_other_listings(audit_store: MetrologyStore) -> None:
    audit_store.write_replay(make_replay())
    audit_store.write_judgment(make_judgment())

    assert audit_store.list_samples() == []
    assert audit_store.list_audit_runs() == []
    assert audit_store.list_replays(PROJECT, replay_set="nope") == []


def test_an_unreadable_sibling_is_skipped_with_a_warning(
    audit_store: MetrologyStore, caplog: pytest.LogCaptureFixture
) -> None:
    keep = audit_store.write_replay(make_replay())
    audit_store.write_judgment(make_judgment())
    (audit_store.store_dir / "replay-20261101-corrupt.json").write_text("{not json")

    with caplog.at_level(logging.WARNING):
        replays = audit_store.list_replays(PROJECT)
        judgments = audit_store.list_judgments(PROJECT)

    assert [rid for rid, _ in replays] == [keep]
    assert len(judgments) == 1
    assert "Skipping unreadable metrology record" in caplog.text
    assert "replay-20261101-corrupt.json" in caplog.text


def test_a_record_written_before_177_loads_unchanged(audit_store: MetrologyStore) -> None:
    """An envelope with neither new sibling field (as 323 wrote it) still validates."""
    run = make_audit_run()
    audit_store.write_audit_run(run)
    path = audit_store.store_dir / f"{run.run_id}.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    for key in ("producer_replay", "pairwise_judgment"):
        raw.pop(key, None)
    path.write_text(json.dumps(raw), encoding="utf-8")

    record: MetrologyRecord = audit_store.load_record(run.run_id)

    assert record.record_type == RECORD_TYPE_AUDIT_FINDING
    assert record.audit_run == run
    assert record.producer_replay is None and record.pairwise_judgment is None
    assert audit_store.list_audit_runs() == [run]


def test_outcome_values_round_trip_as_enums(audit_store: MetrologyStore) -> None:
    audit_store.write_replay(make_replay(outcome=ReplayOutcome.EXHAUSTED))

    ((_, replay),) = audit_store.list_replays(PROJECT)

    assert replay.outcome is ReplayOutcome.EXHAUSTED
