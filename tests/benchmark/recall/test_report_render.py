"""Report text layout (slice 430 API Contracts)."""

from __future__ import annotations

from pathlib import Path

from squadron.benchmark.recall.label_precedence import ResolvedLabels
from squadron.benchmark.recall.recall_store import RecallRecordStore
from squadron.benchmark.recall.report_build import build_report
from squadron.benchmark.recall.report_json import report_json
from squadron.benchmark.recall.report_render import ReportData, ReportRow, render_text
from squadron.benchmark.recall.scoring import recipe_outputs
from squadron.benchmark.recall.scoring_metrics import row_metrics
from squadron.benchmark.recall.scoring_paired import paired_lines
from squadron.benchmark.recall.scoring_select import ImportOnlyResolver
from squadron.core.finding_categories import ReviewCategory
from squadron.core.models import Effort
from squadron.metrology.recall_case_models import RecallCaseSet
from squadron.metrology.recall_label_models import HitVerdict
from squadron.metrology.recall_run_models import RecallRun, StageEntry
from squadron.metrology.store import MetrologyStore
from squadron.recipes.recipe import Recipe
from tests.benchmark.recall.scoring_support import finding, make_case, make_run, review
from tests.benchmark.recall.support import FIXED_NOW

CASE = make_case()
HIT = finding(1, "src/a.py")
OPEN = finding(2, None)


def _data(entry: StageEntry, labels: dict[str, ResolvedLabels]) -> ReportData:
    runs: dict[tuple[str, int], RecallRun] = {(CASE.case_id, 1): make_run(CASE, 1, entry)}
    rows = recipe_outputs(Recipe(name="r", reviewers=("a",)), [CASE], runs, [1], ImportOnlyResolver())
    case_set = RecallCaseSet(name="s", version=1, case_ids=(CASE.case_id,), created=FIXED_NOW)
    return ReportData(
        case_set=case_set,
        known_bugs=2,
        run_indexes=[1],
        rows=[ReportRow(row, row_metrics(row, labels, "s@v1")) for row in rows],
        paired=paired_lines(rows, labels, [1], "s@v1"),
    )


def _labels() -> dict[str, ResolvedLabels]:
    return {
        CASE.case_id: ResolvedLabels(
            hits={HIT.content_key: {"B1": HitVerdict.HIT, "B2": HitVerdict.MISS}}
        )
    }


def test_text_layout_header_table_footer() -> None:
    text = render_text(_data(review("a", (HIT,), case_set="s@v1"), _labels()))
    lines = text.splitlines()
    assert lines[0] == "Case set s v1: 1 cases, 2 known bugs, runs 1..1"
    assert lines[1].startswith("Hit rule: location gate + labels;")
    assert lines[3].startswith("| Recipe | Cases | Runs | Bug-hits | Recall | Bugs found |")
    assert lines[4] == "|" + "---|" * 14
    expected_row = (
        "| r | 1 | 1 | 1/2 | 50% | 1/2 | 1/1 | 0 | 0 | 1.0 | 0 | ungraded | $0.50 unknown "
        "| 1 not scanned |"
    )
    assert lines[5] == expected_row
    assert lines[-1] == (
        "Dropped (harness): 0.  Dropped (leak): 0.  Left out (incomplete stages): none.  "
        "Entries from another set version: 0."
    )


def test_effort_sent_null_prints_not_recorded() -> None:
    assert "a effort sent not recorded" in render_text(_data(review("a", (HIT,)), _labels()))
    assert "a effort sent high" in render_text(
        _data(review("a", (HIT,), effort_sent=Effort.high), _labels())
    )


def test_undecided_prints_ranges() -> None:
    text = render_text(_data(review("a", (HIT, OPEN)), _labels()))
    row = text.splitlines()[5]
    assert "| 1–2/2 | 50–100% |" in row


def _report(tmp_path: Path, recipe: Recipe) -> ReportData:
    store = RecallRecordStore(MetrologyStore(tmp_path / "store"), clock=lambda: FIXED_NOW)
    store.write_case(CASE)
    gate = finding(1, "src/a.py", category=ReviewCategory.CORRECTNESS)
    debt = finding(2, "src/b.py", category=ReviewCategory.TEST_DEBT)
    store.put_run(make_run(CASE, 1, review("a", (gate, debt), case_set="s@v1")))
    case_set = store.write_case_set("s", [CASE.case_id])
    return build_report(store, [recipe], case_set, [1], ImportOnlyResolver())


def test_filtered_recipe_shows_before_and_after_and_lists_not_gating(tmp_path: Path) -> None:
    recipe = Recipe(name="r", reviewers=("a",), keep_categories=(ReviewCategory.CORRECTNESS,))
    data = _report(tmp_path, recipe)
    row = render_text(data).splitlines()[5]
    assert "1.0 (before filter 2.0)" in row and "(before filter " in row.split("|")[5]
    (json_row,) = report_json(data).rows
    assert json_row.findings_per_run_unfiltered == 2.0 and json_row.recall_unfiltered is not None
    assert json_row.not_gating == [f"{CASE.name}/1/a/F2"]


def test_unfiltered_recipe_renders_and_serializes_as_before(tmp_path: Path) -> None:
    data = _report(tmp_path, Recipe(name="r", reviewers=("a",)))
    assert "before filter" not in render_text(data)
    (json_row,) = report_json(data).rows
    assert json_row.findings_per_run_unfiltered is None and json_row.recall_unfiltered is None
    assert json_row.not_gating is None
