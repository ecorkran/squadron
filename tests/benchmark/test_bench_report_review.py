"""Report sections 4-7: review findings, cost and time, absences, sample count (Task 40, D13)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from squadron.benchmark.bench_report_render import render_text
from squadron.benchmark.grade_matrix import RowKey
from squadron.benchmark.leak_scan import LEAK_RULES_VERSION
from squadron.metrology.benchmark_replay_enums import AbsenceClass, ProducerOutcome
from squadron.metrology.floor_stat import FloorStat
from squadron.metrology.grade_models import GradeAbsence
from squadron.metrology.grade_records import CasesNeeded, PairEstimate, SampleSizeEstimate
from tests.benchmark.report_support import (
    FIXED_NOW,
    ReportWorld,
    config,
    make_world,
    review,
)

SPREAD_TWO = FloorStat(min=1, max=3, mean=2.0, stddev=1.0)


def two_configs(
    world: ReportWorld, cases: int, *, a_total: int, b_total: int, **case_kwargs: Any
) -> None:
    for index in range(cases):
        case = world.add_case(f"case-{index}", **case_kwargs)
        for sample in range(2):
            world.add_sample(case, config("opus"), sample, reviews=(review(total=a_total),))
            world.add_sample(
                case, config("sol", effort_sent="medium"), sample, reviews=(review(total=b_total),)
            )


def test_a_case_whose_floor_is_missing_is_no_floor_never_within(tmp_path: Path) -> None:
    world = make_world(tmp_path)
    two_configs(world, 6, a_total=2, b_total=2, floor=None)
    (pair,) = world.build().review_pairs
    assert (pair.no_floor, pair.within, pair.a_more, pair.b_more) == (6, 0, 0, 0)
    assert "no floor 6" in render_text(world.build())


def test_a_delta_equal_to_the_floor_spread_is_beyond_it(tmp_path: Path) -> None:
    world = make_world(tmp_path)
    two_configs(world, 6, a_total=4, b_total=2, floor=SPREAD_TWO)  # delta 2.0, spread 3 - 1
    (pair,) = world.build().review_pairs
    assert (pair.a_more, pair.b_more, pair.within, pair.no_floor) == (6, 0, 0, 0)


def test_a_delta_below_the_spread_is_within_and_the_other_direction_counts_b_more(
    tmp_path: Path,
) -> None:
    world = make_world(tmp_path)
    two_configs(world, 3, a_total=3, b_total=2, floor=SPREAD_TWO)  # delta 1.0 < 2
    two_configs_b_more = make_world(tmp_path / "b")
    two_configs(two_configs_b_more, 3, a_total=1, b_total=4, floor=SPREAD_TWO)  # delta -3
    (within,) = world.build().review_pairs
    (b_more,) = two_configs_b_more.build().review_pairs
    assert within.within == 3 and within.a_more == 0
    assert b_more.b_more == 3 and b_more.a_more == 0


def test_mean_findings_per_replay_by_severity_and_total(tmp_path: Path) -> None:
    world = make_world(tmp_path)
    case = world.add_case("only")
    for sample, severities in enumerate(({"FAIL": 1, "CONCERN": 3}, {"CONCERN": 1})):
        world.add_sample(
            case,
            config("opus"),
            sample,
            reviews=(review(total=sum(severities.values()), severities=severities),),
        )
    row = world.build().findings[0]
    assert row.replays == 2
    assert row.mean_total == pytest.approx(2.5)
    assert row.mean_by_severity == {"CONCERN": pytest.approx(2.0), "FAIL": pytest.approx(0.5)}


def test_unpriced_counts_appear_in_the_cost_section(tmp_path: Path) -> None:
    world = make_world(tmp_path)
    case = world.add_case("only")
    world.add_sample(case, config("opus"), 0, replay={"cost_usd": None})
    world.add_sample(case, config("opus"), 1, replay={"cost_usd": 0.5})
    report = world.build()
    (row,) = report.costs
    assert row.unpriced_producer == 1
    assert row.producer_cost_total == pytest.approx(0.5)
    assert row.producer_cost_mean == pytest.approx(0.5)
    assert "unpriced: 1 producer" in render_text(report)


def test_the_leak_version_count_uses_the_current_constant(tmp_path: Path) -> None:
    from tests.metrology.test_benchmark_replay_models import (
        _clean_leak,  # pyright: ignore[reportPrivateUsage]
    )

    world = make_world(tmp_path)
    case = world.add_case("only")
    older = _clean_leak().model_copy(update={"rules_version": LEAK_RULES_VERSION - 1})
    current = _clean_leak().model_copy(update={"rules_version": LEAK_RULES_VERSION})
    world.add_sample(case, config("opus"), 0, replay={"leak": older})
    world.add_sample(case, config("opus"), 1, replay={"leak": current})
    assert world.build().stale_leak_scans == 1


def test_absences_are_counted_by_class_and_kind(tmp_path: Path) -> None:
    world = make_world(tmp_path)
    case = world.add_case("only")
    world.add_sample(
        case,
        config("opus"),
        0,
        replay={"outcome": ProducerOutcome.COST_CAP, "absence": AbsenceClass.CONFIG},
    )
    world.add_sample(
        case,
        config("opus"),
        1,
        grade_absence=(GradeAbsence.REVIEW_FAILED, AbsenceClass.HARNESS),
    )
    report = world.build()
    found = {(a.absence_class, a.kind, a.count) for a in report.absences}
    assert found == {("config", "replay:cost_cap", 1), ("harness", "grade:review_failed", 1)}
    text = render_text(report)
    assert "config: replay:cost_cap 1" in text
    assert "harness: grade:review_failed 1" in text


def estimate_for(world: ReportWorld) -> SampleSizeEstimate:
    identities = [row.config.identity for row in world.build().costs]
    return SampleSizeEstimate(
        benchmark_id=world.run.benchmark_id,
        case_set=world.run.case_set,
        case_set_version=world.run.case_set_version,
        grader_digest=world.grader.digest,
        n_cases=10,
        samples=3,
        pairs=(
            PairEstimate(
                config_a=identities[0],
                config_b=identities[1],
                within_case_variance=0.1,
                between_case_variance=0.05,
                mdd_now=0.24,
                cases_needed=(
                    CasesNeeded(samples=2, cases=21),
                    CasesNeeded(samples=3, cases=15),
                ),
            ),
        ),
        created_at=FIXED_NOW,
    )


def test_the_sample_count_line_states_n_and_k_and_is_absent_without_an_estimate(
    tmp_path: Path,
) -> None:
    world = make_world(tmp_path)
    two_configs(world, 6, a_total=2, b_total=2)
    without = render_text(world.build())
    assert "sample count" not in without
    with_estimate = render_text(world.build(estimate=estimate_for(world)))
    line = next(line for line in with_estimate.splitlines() if line.startswith("sample count"))
    assert "k=3, n=10" in line
    assert "opus vs sol" in line
    assert "MDD 0.24 at n=10" in line
    assert "21 at k=2" in line and "15 at k=3" in line


def test_an_estimate_from_another_grader_is_not_shown(tmp_path: Path) -> None:
    """The stored estimate is one per benchmark; a re-grade under a new grader outdates it."""
    world = make_world(tmp_path)
    two_configs(world, 6, a_total=2, b_total=2)
    stale = estimate_for(world).model_copy(update={"grader_digest": "0" * 64})

    shown = render_text(world.build(estimate=stale))

    assert "sample count" not in shown


def test_an_estimate_pair_with_no_report_row_is_named_readably_not_by_its_json(
    tmp_path: Path,
) -> None:
    world = make_world(tmp_path)
    two_configs(world, 6, a_total=2, b_total=2)
    estimate = estimate_for(world)
    pair = estimate.pairs[0].model_copy(
        update={"config_b": RowKey("luna", "openai-oauth", None, True, None).identity_text}
    )
    shown = render_text(world.build(estimate=estimate.model_copy(update={"pairs": (pair,)})))
    line = next(line for line in shown.splitlines() if line.startswith("sample count"))
    assert "luna (openai-oauth, effort not sent)" in line
    assert "[" not in line


def test_findings_dropped_as_off_scale_are_counted_and_shown(tmp_path: Path) -> None:
    world = make_world(tmp_path)
    case = world.add_case("case-0")
    for sample in range(2):
        world.add_sample(case, config("opus"), sample, reviews=(review(total=2, unnormalized=3),))
    report = world.build()
    assert report.findings[0].unnormalized == 6
    assert "6 dropped as off-scale" in render_text(report)


def test_no_dropped_findings_adds_nothing_to_the_line(tmp_path: Path) -> None:
    world = make_world(tmp_path)
    case = world.add_case("case-0")
    world.add_sample(case, config("opus"), 0, reviews=(review(total=2),))
    assert "off-scale" not in render_text(world.build())
