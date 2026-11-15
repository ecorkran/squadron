"""The measured sample-count line in the yield report (slice 425 Task 44, D15)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from squadron.benchmark.grade_matrix import RowKey
from squadron.benchmark.yield_report import YieldReport, build_yield, render_json, render_text
from squadron.metrology.benchmark_models import CaseSet
from squadron.metrology.grade_records import CasesNeeded, PairEstimate, SampleSizeEstimate
from tests.benchmark.test_yield_report import SAMPLES, TARGET, sample_records

NOW = datetime(2026, 11, 14, tzinfo=UTC)
CASE_SETS = [CaseSet(name="fixes", version=1, case_ids=("case-aaaaaaaaaaaaaaaa",), created_at=NOW)]


def identity(model: str, effort: str = "high") -> str:
    return RowKey(model, "sdk", effort, True, None).identity_text


def pair(a: str, b: str, mdd: float, needed: dict[int, int]) -> PairEstimate:
    return PairEstimate(
        config_a=identity(a),
        config_b=identity(b),
        within_case_variance=0.1,
        between_case_variance=0.05,
        mdd_now=mdd,
        cases_needed=tuple(CasesNeeded(samples=k, cases=n) for k, n in needed.items()),
    )


def estimate(*pairs: PairEstimate, samples: int = 3, case_set: str = "fixes") -> SampleSizeEstimate:
    return SampleSizeEstimate(
        benchmark_id="bench-3f9c",
        case_set=case_set,
        case_set_version=1,
        grader_digest="a" * 64,
        n_cases=10,
        samples=samples,
        pairs=pairs,
        created_at=NOW,
    )


def build(found: SampleSizeEstimate | None) -> YieldReport:
    return build_yield(
        sample_records(),
        CASE_SETS,
        SAMPLES,
        TARGET,
        lambda name: found if found is not None and name == found.case_set else None,
    )


def test_an_estimate_shows_both_the_analytic_line_and_the_measured_one() -> None:
    text = render_text(build(estimate(pair("opus", "sol", 0.24, {1: 30, 2: 21, 3: 15, 5: 10}))))
    lines = text.splitlines()
    assert any(line.startswith("separability alpha (k=3 samples") for line in lines)
    measured = next(line for line in lines if line.startswith("measured ("))
    assert measured.startswith("measured (bench-3f9c, n=10, k=3) fixes: ")
    assert "opus (sdk, effort high) vs sol (sdk, effort high) needs the most cases" in measured
    assert "MDD 0.24 now" in measured
    assert "need 15 cases at k=3" in measured
    assert lines.index(measured) > max(
        i for i, line in enumerate(lines) if line.startswith("separability")
    )


def test_with_two_pairs_the_line_shows_the_one_needing_more_cases_at_that_k() -> None:
    first = pair("opus", "sol", 0.24, {1: 30, 2: 21, 3: 15, 5: 10})
    second = pair("opus", "luna", 0.31, {1: 60, 2: 40, 3: 27, 5: 16})
    text = render_text(build(estimate(first, second)))
    measured = next(line for line in text.splitlines() if line.startswith("measured ("))
    assert "vs luna (sdk" in measured and "sol" not in measured
    assert "MDD 0.31 now" in measured and "need 27 cases at k=3" in measured


def test_a_k_that_is_not_projected_uses_the_nearest_k_below_and_says_so() -> None:
    line = render_text(build(estimate(pair("a", "b", 0.2, {1: 30, 2: 21, 3: 15, 5: 10}), samples=4)))
    measured = next(item for item in line.splitlines() if item.startswith("measured ("))
    assert "k=4" in measured.split(")")[0]
    assert "need 15 cases at k=3" in measured


def test_an_estimate_with_no_projected_k_at_or_below_its_k_is_an_error() -> None:
    found = estimate(pair("a", "b", 0.2, {5: 10}), samples=3)
    with pytest.raises(ValueError, match="projects no k at or below"):
        render_text(build(found))


def test_without_an_estimate_the_output_is_unchanged() -> None:
    baseline = build_yield(sample_records(), CASE_SETS, SAMPLES, TARGET)
    without = build(None)
    assert render_text(without) == render_text(baseline)
    assert render_json(without) == render_json(baseline)
    assert "measured (" not in render_text(without)
    assert "measured" not in json.loads(render_json(without))


def test_an_estimate_for_a_case_set_the_report_does_not_involve_adds_nothing() -> None:
    other = estimate(pair("a", "b", 0.2, {3: 15}), case_set="other-set")
    assert render_text(build(other)) == render_text(build(None))


def test_the_json_carries_the_measured_line() -> None:
    payload = json.loads(
        render_json(build(estimate(pair("opus", "sol", 0.24, {1: 30, 2: 21, 3: 15, 5: 10}))))
    )
    (line,) = payload["measured"]
    assert line["benchmark_id"] == "bench-3f9c"
    assert (line["n_cases"], line["samples"]) == (10, 3)
    assert (line["cases_needed"], line["needed_at_samples"]) == (15, 3)
    assert line["mdd_now"] == 0.24
    assert line["pair"] == [identity("opus"), identity("sol")]
