"""The judge plan's pairs, forfeits and counts (slice 426, Task 32)."""

from __future__ import annotations

from pathlib import Path

from squadron.benchmark.diff_judge_runner import judge_lock_path
from squadron.metrology.benchmark_replay_enums import ProducerOutcome
from tests.benchmark.diff_judge_run_support import (
    ScriptedDispatcher,
    World,
    case_named,
    make_world,
    plan_of,
    run_plan,
)
from tests.benchmark.diff_judge_support import diff_text

# A hand-built run:
#   case "fits":   opus and sol at k = 2, no absence  -> 2 cross + 4 reference pairs = 6, no forfeit
#   case "forfeit": opus k = 1, sol absent (no_commit) -> 1 cross + 2 reference pairs = 3, all forfeits
#                   except opus vs reference
#   case "big":    its reference diff is huge          -> over size
#   case "harness": sol has a harness absence          -> harness-absent
CASES = {
    "fits": {"opus": 2, "sol": 2},
    "forfeit": {"opus": 1},
    "big": {"opus": 1, "sol": 1},
    "harness": {"opus": 1},
}
ABSENT = {
    "forfeit": {"sol": ProducerOutcome.NO_COMMIT},
    "harness": {"sol": ProducerOutcome.NO_RUN_STATE},
}
SMALL_LIMIT = 4000


def _world(tmp_path: Path) -> World:
    world = make_world(tmp_path, cases=CASES, absent=ABSENT)
    huge = b"".join(diff_text(f"huge{n}") for n in range(200))
    world.reference_diffs[case_named(world, 2).case_id] = huge
    return world


def test_the_plan_counts_match_a_hand_built_run(tmp_path: Path) -> None:
    world = _world(tmp_path)

    plan = plan_of(world, limit=SMALL_LIMIT)

    assert [cp.case.case_id for cp in plan.cases] == [
        case_named(world, 0).case_id,
        case_named(world, 1).case_id,
    ]
    assert [c.case_id for c, _ in plan.over_size] == [case_named(world, 2).case_id]
    assert [(c.case_id, reason) for c, reason in plan.harness_absent] == [
        (case_named(world, 3).case_id, "no_run_state")
    ]
    fits, forfeit = plan.cases
    assert len(fits.pairs) == 2 + 4 and fits.forfeits == 0
    assert len(forfeit.pairs) == 1 + 2 and forfeit.forfeits == 2  # sol's two pairs are forfeits
    assert plan.pairs == 9 and plan.forfeits == 2
    assert plan.calls == 2 * (9 - 2)
    assert plan.case_count == 4


def test_a_recorded_pair_is_excluded_from_the_pairs_needing_calls(tmp_path: Path) -> None:
    world = _world(tmp_path)
    first = plan_of(world, limit=SMALL_LIMIT)
    result, _ = run_plan(world, first, ScriptedDispatcher(), lock_root=tmp_path / "locks")
    assert result.summary.judged > 0

    again = plan_of(world, limit=SMALL_LIMIT)

    assert again.pairs == 0 and again.calls == 0
    assert [cp.case.case_id for cp in again.cases] == [cp.case.case_id for cp in first.cases]


def test_a_case_whose_limit_now_fits_is_planned_for_judging(tmp_path: Path) -> None:
    world = _world(tmp_path)
    big = case_named(world, 2)

    tight = plan_of(world, limit=SMALL_LIMIT)
    roomy = plan_of(world)

    assert big.case_id in {c.case_id for c, _ in tight.over_size}
    assert big.case_id not in {c.case_id for c, _ in roomy.over_size}
    assert big.case_id in {cp.case.case_id for cp in roomy.cases}


def test_the_plan_names_each_over_size_case_with_its_length_and_contestant(tmp_path: Path) -> None:
    plan = plan_of(_world(tmp_path), limit=SMALL_LIMIT)

    ((_, over),) = plan.over_size
    assert over.longest_chars > SMALL_LIMIT
    assert over.contestant.startswith("reference:")


def test_the_lock_file_is_the_judges_own(tmp_path: Path) -> None:
    path = judge_lock_path(tmp_path, "bench-3f9c0a1b2c3d4e5f")

    assert path.name == "bench-3f9c0a1b2c3d4e5f.judge.lock"
