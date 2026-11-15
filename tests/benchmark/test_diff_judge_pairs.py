"""Contestants, pairing, forfeits and judgeability (slice 426, Task 27)."""

from __future__ import annotations

from datetime import UTC, datetime
from math import comb

import pytest

from squadron.benchmark.diff_pairs import (
    REFERENCE_PREFIX,
    ContestantKind,
    Pair,
    ReferenceAbsentError,
    case_judgeable,
    contestants_for,
    forfeit_for,
    forfeit_judgment,
    pairs_for,
)
from squadron.metrology.replay_models import PairOutcome
from tests.benchmark.diff_judge_support import (
    CONFIG_ABSENCES,
    HARNESS_ABSENCES,
    diff_text,
    grid,
    replay_input,
)
from tests.benchmark.slice_case_support import judge_ref
from tests.benchmark.slice_runner_support import slice_case

CASE = slice_case()
REFERENCE_DIFF = diff_text("reference")


def _pairs(aliases: dict[str, int]) -> list[Pair]:
    return pairs_for(contestants_for(CASE, grid(CASE, aliases), REFERENCE_DIFF))


def test_two_configs_at_k3_give_nine_pairs() -> None:
    assert len(_pairs({"opus": 3, "sol": 3})) == 9


@pytest.mark.parametrize("configs, k", [(2, 2), (3, 2), (3, 3), (4, 1)])
def test_c_configs_at_k_samples_give_the_designs_count(configs: int, k: int) -> None:
    aliases = {f"cfg{n}": k for n in range(configs)}

    assert len(_pairs(aliases)) == k * comb(configs, 2) + k * configs


def test_no_pair_is_within_one_config() -> None:
    for pair in _pairs({"opus": 3, "sol": 2}):
        assert pair.a.config != pair.b.config


def test_cross_config_pairs_match_sample_numbers() -> None:
    cross = [p for p in _pairs({"opus": 3, "sol": 3}) if not p.versus_reference]

    assert [(p.a.sample, p.b.sample) for p in cross] == [(1, 1), (2, 2), (3, 3)]


def test_each_replay_appears_against_the_reference_once() -> None:
    pairs = _pairs({"opus": 2, "sol": 2})
    against_reference = [p.a.ref for p in pairs if p.versus_reference]

    assert len(against_reference) == len(set(against_reference)) == 4
    assert all(
        p.b.ref == f"{REFERENCE_PREFIX}{CASE.reference_sha}" for p in pairs if p.versus_reference
    )


def test_pair_order_is_deterministic() -> None:
    inputs = grid(CASE, {"opus": 2, "sol": 2})
    forward = pairs_for(contestants_for(CASE, inputs, REFERENCE_DIFF))
    backward = pairs_for(contestants_for(CASE, list(reversed(inputs)), REFERENCE_DIFF))

    assert [(p.a.ref, p.b.ref) for p in forward] == [(p.a.ref, p.b.ref) for p in backward]


def test_a_config_with_a_missing_sample_number_pairs_only_the_samples_that_exist() -> None:
    inputs = [*grid(CASE, {"opus": 3}), *[replay_input(CASE, "sol", s) for s in (1, 3)]]

    cross = [
        p for p in pairs_for(contestants_for(CASE, inputs, REFERENCE_DIFF)) if not p.versus_reference
    ]

    assert sorted((p.a.sample, p.b.sample) for p in cross) == [(1, 1), (3, 3)]


@pytest.mark.parametrize("absence", CONFIG_ABSENCES)
def test_each_config_absence_forfeits_to_the_other_side(absence: object) -> None:
    inputs = [
        replay_input(CASE, "opus", 1),
        replay_input(CASE, "sol", 1, outcome=absence),  # type: ignore[arg-type]
    ]
    pairs = pairs_for(contestants_for(CASE, inputs, REFERENCE_DIFF))
    cross = next(p for p in pairs if not p.versus_reference)
    against_reference = next(p for p in pairs if p.versus_reference and p.a.label == "sol")

    assert cross.a.label == "opus" or cross.b.label == "opus"
    winner = PairOutcome.A if cross.a.label == "opus" else PairOutcome.B
    assert forfeit_for(cross) is winner
    assert forfeit_for(against_reference) is PairOutcome.B  # the reference wins


def test_both_sides_absent_is_a_tie() -> None:
    inputs = [
        replay_input(CASE, "opus", 1, outcome=CONFIG_ABSENCES[0]),
        replay_input(CASE, "sol", 1, outcome=CONFIG_ABSENCES[1]),
    ]
    cross = next(
        p for p in pairs_for(contestants_for(CASE, inputs, REFERENCE_DIFF)) if not p.versus_reference
    )

    assert forfeit_for(cross) is PairOutcome.TIE


def test_two_present_sides_are_not_a_forfeit() -> None:
    assert all(forfeit_for(p) is None for p in _pairs({"opus": 1, "sol": 1}))


def test_an_absent_reference_raises() -> None:
    contestants = contestants_for(CASE, grid(CASE, {"opus": 1}), REFERENCE_DIFF)
    reference = next(c for c in contestants if c.kind is ContestantKind.REFERENCE)
    broken = [c for c in contestants if c is not reference] + [
        type(reference)(**{**reference.__dict__, "diff": None, "absence": None})
    ]
    pair = next(p for p in pairs_for(broken) if p.versus_reference)

    with pytest.raises(ReferenceAbsentError):
        forfeit_for(pair)


def test_a_harness_absence_on_any_replay_makes_the_case_not_judgeable_naming_the_reason() -> None:
    for absence in HARNESS_ABSENCES:
        replays = [replay_input(CASE, "opus", 1), replay_input(CASE, "sol", 1, outcome=absence)]

        verdict = case_judgeable(replays)

        assert not verdict.judgeable
        assert verdict.reason == absence.value


def test_config_absences_leave_the_case_judgeable() -> None:
    replays = [replay_input(CASE, "opus", 1, outcome=CONFIG_ABSENCES[2])]

    assert case_judgeable(replays) == (True, None)


def test_a_forfeit_validates_as_a_judgment_with_no_calls() -> None:
    inputs = [replay_input(CASE, "opus", 1), replay_input(CASE, "sol", 1, outcome=CONFIG_ABSENCES[0])]
    pair = next(
        p for p in pairs_for(contestants_for(CASE, inputs, REFERENCE_DIFF)) if not p.versus_reference
    )
    outcome = forfeit_for(pair)
    assert outcome is not None

    judgment = forfeit_judgment(
        benchmark_id="bench-3f9c0a1b2c3d4e5f",
        case_id=CASE.case_id,
        pair=pair,
        outcome=outcome,
        diff_hashes={pair.a.ref: "a" * 64, pair.b.ref: "b" * 64},
        judge=judge_ref(),
        max_prompt_chars=400000,
        created_at=datetime(2026, 11, 15, tzinfo=UTC),
    )

    assert judgment.forfeit and judgment.first_call is None and judgment.second_call is None
    present = pair.a if pair.a.present else pair.b
    absent = pair.b if pair.a.present else pair.a
    hashes = {pair.a.ref: judgment.a_diff, pair.b.ref: judgment.b_diff}
    assert hashes[present.ref] is not None
    assert hashes[absent.ref] is None


def test_contestants_refuse_a_harness_absent_or_diffless_committed_replay() -> None:
    harness = replay_input(CASE, "opus", 1, outcome=HARNESS_ABSENCES[0])
    with pytest.raises(ValueError, match="harness absence"):
        contestants_for(CASE, [harness], REFERENCE_DIFF)
    committed = replay_input(CASE, "opus", 1)
    with pytest.raises(ValueError, match="no diff"):
        contestants_for(CASE, [committed._replace(diff=None)], REFERENCE_DIFF)
