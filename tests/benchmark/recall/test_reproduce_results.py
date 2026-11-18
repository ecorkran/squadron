"""The report reproduces RESULTS.md sections 1 and 5 from imported records (slice 430)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from squadron.benchmark.recall.recall_services import RecallServices
from squadron.benchmark.recall.recipe import Recipe, load_recipe
from squadron.benchmark.recall.report_build import build_report, resolved_labels
from squadron.benchmark.recall.report_render import ReportData
from squadron.benchmark.recall.scoring_select import ImportOnlyResolver
from squadron.metrology.recall_label_models import HitVerdict
from tests.benchmark.recall.committed import RECIPES_DIR, imported_services
from tests.benchmark.recall.support import invoke_recall

SECTION_1 = ("haiku-xhigh", "sol", "sonnet-high", "sonnet")
SECTION_5_REVIEWERS = ("haiku-xhigh", "sol", "sonnet-high", "sonnet")


@pytest.fixture(scope="module")
def services(tmp_path_factory: pytest.TempPathFactory) -> RecallServices:
    return imported_services(tmp_path_factory.mktemp("recall"))


def _report(services: RecallServices, recipes: list[Recipe], set_ref: str, runs: int) -> ReportData:
    case_set = services.store.resolve_set(set_ref)
    return build_report(
        services.store, recipes, case_set, list(range(1, runs + 1)), ImportOnlyResolver()
    )


def _committed(*names: str) -> list[Recipe]:
    return [load_recipe(RECIPES_DIR / f"{name}.yaml") for name in names]


def test_section_1_bug_hits_and_runs_with_a_hit(services: RecallServices) -> None:
    data = _report(services, _committed(*SECTION_1), "real-bugs-original", 3)
    metrics = [row.metrics for row in data.rows]
    assert [row.outputs.label for row in data.rows] == list(SECTION_1)
    assert [(m.bug_hits.low, m.bug_hits.high, m.bug_slots) for m in metrics] == [
        (16, 16, 42), (12, 12, 42), (7, 7, 42), (4, 4, 42),
    ]  # fmt: skip
    assert [(m.runs_with_hit.low, m.pairs) for m in metrics] == [(14, 30), (12, 30), (7, 30), (4, 30)]
    assert all(m.leaks == {"not_scanned": 30} for m in metrics)


def test_section_1_without_u103(services: RecallServices) -> None:
    data = _report(services, _committed(*SECTION_1), "real-bugs-original-no-u103", 3)
    assert [(row.metrics.bug_hits.low, row.metrics.bug_slots) for row in data.rows] == [
        (13, 39), (9, 39), (4, 39), (1, 39),
    ]  # fmt: skip


def _known_kept(services: RecallServices, data: ReportData) -> int:
    """Run-1 kept findings carrying a HIT label, summed over the reviewers (section 5)."""
    labels = resolved_labels(services.store.list_labels())
    row = data.rows[0].outputs
    return sum(
        1
        for pair in row.pairs
        for reviewer in pair.reviewers
        for finding in reviewer.lower
        if HitVerdict.HIT in labels[pair.case.case_id].hits.get(finding.content_key, {}).values()
    )


@pytest.mark.parametrize(
    ("combs", "known_kept", "bugs_found"),
    [
        ((), 14, 8),
        (("opus-high",), 14, 8),
        (("luna-r",), 14, 8),
        (("sol",), 10, None),
        (("sonnet-high",), 8, None),
    ],
)
def test_section_5_known_kept(
    services: RecallServices, combs: tuple[str, ...], known_kept: int, bugs_found: int | None
) -> None:
    recipe = Recipe(name="fan-out", reviewers=SECTION_5_REVIEWERS, combs=combs)
    data = _report(services, [recipe], "real-bugs-original", 1)
    assert len(data.rows) == 1 and not data.rows[0].outputs.left_out
    assert _known_kept(services, data) == known_kept
    if bugs_found is not None:
        assert data.rows[0].metrics.bugs_found.low == bugs_found


def test_compound_recipes_need_no_calls_and_pool_is_the_mean(services: RecallServices) -> None:
    data = _report(
        services,
        _committed("haiku-sol-opus", "haiku-sol-pool", "haiku-xhigh", "sol"),
        "real-bugs-original",
        1,
    )
    rows = {row.outputs.label: row for row in data.rows}
    assert all(not row.outputs.left_out for row in data.rows)
    pool, haiku, sol = (rows[name].metrics for name in ("haiku-sol-pool", "haiku-xhigh", "sol"))
    assert pool.bug_hits.low == (haiku.bug_hits.low + sol.bug_hits.low) / 2
    assert pool.findings_per_run == pytest.approx((haiku.findings_per_run + sol.findings_per_run) / 2)


def test_report_command_prints_section_1(services: RecallServices) -> None:
    recipes = [arg for name in SECTION_1 for arg in ("--recipe", str(RECIPES_DIR / f"{name}.yaml"))]
    result = invoke_recall(services, "report", "--set", "real-bugs-original", "--runs", "3", *recipes)
    assert result.exit_code == 0, result.output
    assert "| haiku-xhigh | 10 | 3 | 16/42 | 38% |" in result.output
    assert "Left out (incomplete stages): none." in result.output
    as_json = invoke_recall(
        services, "report", "--set", "real-bugs-original", "--runs", "3", "--json", *recipes
    )
    document = json.loads(as_json.output)
    assert document["rows"][0]["bug_hits"] == {"low": 16.0, "high": 16.0}


def test_report_refuses_a_bad_recipe(services: RecallServices, tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("name: x\nreviewers: []\n", encoding="utf-8")
    result = invoke_recall(services, "report", "--set", "real-bugs", "--recipe", str(bad))
    assert result.exit_code == 1
    assert "Error:" in result.output
