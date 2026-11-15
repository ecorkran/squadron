"""The pairwise section's text and JSON (slice 426, Task 38)."""

from __future__ import annotations

import json
from pathlib import Path

from squadron.benchmark.bench_report_render import render_json, render_text
from squadron.benchmark.report_models import BenchmarkReport
from squadron.metrology.benchmark_replay_enums import AbsenceClass, ProducerOutcome
from squadron.metrology.replay_models import PairOutcome
from squadron.metrology.slice_case_models import DiffJudgment
from tests.benchmark.pairwise_support import (
    OPUS,
    SOL,
    as_slice,
    cross,
    over_size_record,
    reference_ref,
    slice_world,
    verdict_judgment,
)
from tests.benchmark.report_support import ReportWorld, fixture_world, make_world
from tests.benchmark.slice_case_support import judge_ref

A, B, T = PairOutcome.A, PairOutcome.B, PairOutcome.TIE
LIMIT = 400000


def _judged_world(tmp_path: Path, cases: int = 6) -> tuple[ReportWorld, list[DiffJudgment]]:
    """``cases`` judged slice cases, opus ahead on four and sol on two, plus each side against
    the reference, so every contestant has a win and a loss."""
    world = make_world(tmp_path, samples=1)
    found, ids = slice_world(world, cases=cases, samples=1)
    judgments = []
    for n, case in enumerate(found):
        judgments += cross(case, ids, [A if n < 4 else B])
        judgments.append(
            verdict_judgment(case, ids.of(case, "opus", 0), reference_ref(case), A if n % 2 else B)
        )
        judgments.append(
            verdict_judgment(case, ids.of(case, "sol", 0), reference_ref(case), B if n % 2 else A)
        )
    return world, judgments


def test_the_section_follows_the_design_layout_for_a_stored_fixture(tmp_path: Path) -> None:
    world, judgments = _judged_world(tmp_path)
    world_extra = as_slice(world, world.add_case("big"))
    for cfg in (OPUS, SOL):
        world.add_sample(world_extra, cfg, 0)
    harness = as_slice(world, world.add_case("harness"))
    world.add_sample(harness, OPUS, 0)
    world.add_sample(
        harness,
        SOL,
        0,
        replay={"outcome": ProducerOutcome.NO_RUN_STATE, "absence": AbsenceClass.HARNESS},
    )

    text = render_text(
        world.build(judgments=judgments, over_size=[over_size_record(world_extra, limit=LIMIT)])
    )

    lines = text.splitlines()
    start = next(
        i for i, line in enumerate(lines) if line.startswith("pairwise (judge gpt-judge, prompt ")
    )
    assert lines[start - 2].startswith("  opus vs sol: beyond floor")  # after the review findings
    header = lines[start]
    assert header.endswith("strength   W   L   T  inc  inv  forfeit  pairs")
    rows = lines[start + 1 : start + 4]
    assert rows[0].lstrip().startswith("opus") and rows[1].lstrip().startswith("sol")
    assert rows[2].lstrip().startswith("reference") and "(reference line, not ranked)" in rows[2]
    assert lines[start + 4].lstrip().startswith("opus vs sol   d ")
    assert "(n=6 cases)" in lines[start + 4]
    assert lines[start + 5] == (
        f"judged 6 · over size 1 (limit {LIMIT} chars) · harness-absent 1 · pending 0"
    )
    assert text.index("cost / turns / time") > text.index("pairwise (judge")


def test_two_judges_list_the_latest_first_and_name_the_other(tmp_path: Path) -> None:
    world, judgments = _judged_world(tmp_path, cases=2)
    other = judge_ref(alias="old-judge", prompt_hash="9" * 64)
    old = [
        verdict_judgment(j_case, j.a, j.b, j.outcome or A, judge=other, at=-5)  # type: ignore[arg-type]
        for j in judgments
        for j_case in [world.cases[j.case_id]]
    ]

    report = world.build(judgments=[*old, *judgments])

    assert report.pairwise is not None
    assert report.pairwise.judge_alias == "gpt-judge"
    assert [(o.alias, o.judgments) for o in report.pairwise.others] == [("old-judge", len(old))]
    text = render_text(report)
    assert "other judges: old-judge (prompt 99999999) " in text
    assert text.index("pairwise (judge gpt-judge") < text.index("other judges")


def test_a_case_with_an_over_size_record_and_later_judgments_counts_as_judged(
    tmp_path: Path,
) -> None:
    world, judgments = _judged_world(tmp_path, cases=2)
    case = next(iter(world.cases.values()))
    stale = over_size_record(case, limit=1000, at=-10)  # written before the limit was raised

    report = world.build(judgments=judgments, over_size=[stale])

    assert report.pairwise is not None
    assert report.pairwise.counts.over_size == 0
    assert report.pairwise.counts.judged == 2


def test_failed_pairs_pending_are_counted_for_judged_cases(tmp_path: Path) -> None:
    world = make_world(tmp_path, samples=1)
    (case,), ids = slice_world(world, cases=1, samples=1)

    report = world.build(judgments=cross(case, ids, [A]))  # the two reference pairs failed

    assert report.pairwise is not None
    assert report.pairwise.counts.pending == 2
    assert "pending 2" in render_text(report)


def test_a_strength_without_a_finite_value_prints_its_reason(tmp_path: Path) -> None:
    world = make_world(tmp_path, samples=1)
    (case,), ids = slice_world(world, cases=1, samples=1)

    text = render_text(world.build(judgments=cross(case, ids, [A])))

    assert "no finite strength: never lost" in text


def test_the_pairwise_json_loads_back_and_carries_no_composite_field(tmp_path: Path) -> None:
    world, judgments = _judged_world(tmp_path)
    report = world.build(judgments=judgments)

    payload = json.loads(render_json(report))
    assert BenchmarkReport.model_validate_json(render_json(report)) == report

    def keys(node: object) -> set[str]:
        if isinstance(node, dict):
            return {str(k) for k in node} | {name for v in node.values() for name in keys(v)}
        if isinstance(node, list):
            return {name for v in node for name in keys(v)}
        return set()

    pairwise_keys = keys(payload["pairwise"])
    assert {"configs", "reference", "pairs", "counts", "others"} <= pairwise_keys
    for word in ("score", "composite", "overall", "combined"):
        assert not any(word in key for key in pairwise_keys), word


def test_a_fix_only_report_has_no_pairwise_section(tmp_path: Path) -> None:
    report = fixture_world(tmp_path).build()

    assert report.pairwise is None
    assert "pairwise" not in render_text(report)
    assert "pairwise" not in json.loads(render_json(report))


def test_slice_cases_without_judgments_have_no_pairwise_section(tmp_path: Path) -> None:
    world = make_world(tmp_path, samples=1)
    slice_world(world, cases=2, samples=1)

    assert world.build().pairwise is None
