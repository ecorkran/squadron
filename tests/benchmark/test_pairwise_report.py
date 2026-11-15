"""The pairwise reduction, with hand-computed values (slice 426, Task 37)."""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.benchmark.pairwise_models import PairwiseSection
from squadron.metrology.grade_models import PairVerdict
from squadron.metrology.replay_models import PairOutcome
from squadron.metrology.slice_case_models import DiffJudgment
from squadron.replay.bradley_terry import NEVER_LOST
from tests.benchmark.pairwise_support import (
    OPUS,
    SOL,
    as_slice,
    cross,
    reference_ref,
    slice_world,
    verdict_judgment,
)
from tests.benchmark.report_support import ReportWorld, make_world

A, B, T = PairOutcome.A, PairOutcome.B, PairOutcome.TIE
I = PairOutcome.INCONSISTENT  # noqa: E741 - the design's name for the outcome


def _section(world: ReportWorld, judgments: list[DiffJudgment]) -> PairwiseSection:
    report = world.build(judgments=judgments)
    assert report.pairwise is not None
    return report.pairwise


def test_a_case_with_wins_ties_and_one_inconsistent_pair_gives_the_hand_computed_difference(
    tmp_path: Path,
) -> None:
    """Three sample-matched pairs for one case: opus wins one, one is a tie, one inconsistent.

    w(c) = (1 + 0.5) / 2 = 0.75 over the two counted pairs (the inconsistent one is left out),
    so d(c) = 2 * 0.75 - 1 = 0.5.
    """
    world = make_world(tmp_path, samples=3)
    (case,), ids = slice_world(world, cases=1, samples=3)

    section = _section(world, cross(case, ids, [A, T, I]))

    (pair,) = section.pairs
    assert pair.n_cases == 1
    assert pair.mean_difference == pytest.approx(0.5)
    assert pair.verdict is PairVerdict.TOO_FEW_CASES
    assert (pair.low, pair.high) == (None, None)


def test_a_pair_of_configs_whose_interval_spans_zero_is_not_distinguishable(tmp_path: Path) -> None:
    world = make_world(tmp_path, samples=1)
    cases, ids = slice_world(world, cases=6, samples=1)
    judgments = [
        verdict_judgment(case, ids.of(case, "opus", 0), ids.of(case, "sol", 0), A if n % 2 else B)
        for n, case in enumerate(cases)
    ]  # d = +1, -1, +1, -1, +1, -1: mean 0

    (pair,) = _section(world, judgments).pairs

    assert pair.n_cases == 6
    assert pair.mean_difference == pytest.approx(0.0)
    assert pair.verdict is PairVerdict.NOT_DISTINGUISHABLE
    assert pair.low is not None and pair.high is not None and pair.low < 0 < pair.high


def test_a_config_that_wins_every_case_is_ahead(tmp_path: Path) -> None:
    world = make_world(tmp_path, samples=1)
    cases, ids = slice_world(world, cases=6, samples=1)
    judgments = [j for case in cases for j in cross(case, ids, [A])]

    (pair,) = _section(world, judgments).pairs

    assert pair.mean_difference == pytest.approx(1.0)
    assert pair.verdict is PairVerdict.A_AHEAD


def test_one_case_is_too_few_cases(tmp_path: Path) -> None:
    world = make_world(tmp_path, samples=1)
    (case,), ids = slice_world(world, cases=1, samples=1)

    (pair,) = _section(world, cross(case, ids, [B])).pairs

    assert pair.verdict is PairVerdict.TOO_FEW_CASES
    assert pair.mean_difference == pytest.approx(-1.0)


def test_a_case_dropped_at_grading_is_excluded(tmp_path: Path) -> None:
    world = make_world(tmp_path, samples=1)
    (kept,), ids = slice_world(world, cases=1, samples=1)
    dropped = as_slice(world, world.add_case("dropped", reference_passes=False))
    dropped_ids = {
        alias: world.add_sample(dropped, cfg, 0, passed=True)
        for alias, cfg in (("opus", OPUS), ("sol", SOL))
    }
    judgments = [
        *cross(kept, ids, [A]),
        verdict_judgment(dropped, dropped_ids["opus"], dropped_ids["sol"], B),
    ]

    report = world.build(judgments=judgments)

    assert report.pairwise is not None
    (pair,) = report.pairwise.pairs
    assert pair.n_cases == 1  # the dropped case's judgment does not count
    assert pair.mean_difference == pytest.approx(1.0)
    assert report.cases_compared == 1


def test_the_reference_is_fitted_but_never_ranked(tmp_path: Path) -> None:
    world = make_world(tmp_path, samples=1)
    (case,), ids = slice_world(world, cases=1, samples=1)
    ref = reference_ref(case)
    judgments = [
        verdict_judgment(case, ids.of(case, "opus", 0), ref, A),
        verdict_judgment(case, ids.of(case, "sol", 0), ref, B),
        verdict_judgment(case, ids.of(case, "opus", 0), ids.of(case, "sol", 0), T),
        verdict_judgment(case, ids.of(case, "opus", 0), ref, B, at=1),
        verdict_judgment(case, ids.of(case, "sol", 0), ref, A, at=1),
    ]

    section = _section(world, judgments)

    assert section.reference is not None and section.reference.strength is not None
    assert {row.label for row in section.configs} == {"opus", "sol"}  # no row for the reference
    assert all("reference" not in row.identity for row in section.configs)


def test_a_strength_with_no_finite_value_carries_177s_reason(tmp_path: Path) -> None:
    world = make_world(tmp_path, samples=1)
    (case,), ids = slice_world(world, cases=1, samples=1)
    judgments = [
        verdict_judgment(case, ids.of(case, "opus", 0), ids.of(case, "sol", 0), A),
        verdict_judgment(case, ids.of(case, "opus", 0), reference_ref(case), A),
    ]  # opus never loses

    section = _section(world, judgments)

    opus = next(row for row in section.configs if row.label == "opus")
    assert opus.strength is None and opus.reason == NEVER_LOST


def test_forfeits_count_in_the_configs_tallies(tmp_path: Path) -> None:
    world = make_world(tmp_path, samples=1)
    (case,), ids = slice_world(world, cases=1, samples=1)
    judgments = [
        verdict_judgment(case, ids.of(case, "opus", 0), ids.of(case, "sol", 0), A, forfeit=True),
        verdict_judgment(case, ids.of(case, "sol", 0), reference_ref(case), A),
    ]

    section = _section(world, judgments)

    opus = next(row for row in section.configs if row.label == "opus")
    sol = next(row for row in section.configs if row.label == "sol")
    assert (opus.wins, opus.forfeits, opus.pairs) == (1, 1, 1)
    assert (sol.losses, sol.wins, sol.forfeits, sol.pairs) == (1, 1, 1, 2)


def test_tallies_keep_ties_inconsistent_and_invalid_apart(tmp_path: Path) -> None:
    world = make_world(tmp_path, samples=4)
    (case,), ids = slice_world(world, cases=1, samples=4)

    section = _section(world, cross(case, ids, [A, T, I, PairOutcome.INVALID]))

    opus = next(row for row in section.configs if row.label == "opus")
    assert (opus.wins, opus.ties, opus.inconsistent, opus.invalid, opus.pairs) == (1, 1, 1, 1, 4)


def test_the_models_hold_no_composite_field() -> None:
    from squadron.benchmark import pairwise_models

    forbidden = ("score", "composite", "overall", "combined", "total")
    for name in dir(pairwise_models):
        model = getattr(pairwise_models, name)
        for field in getattr(model, "model_fields", {}):
            assert not any(word in field for word in forbidden), f"{name}.{field}"
