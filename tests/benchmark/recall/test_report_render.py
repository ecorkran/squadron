"""Report text layout (slice 430 API Contracts)."""

from __future__ import annotations

from squadron.benchmark.recall.label_precedence import ResolvedLabels
from squadron.benchmark.recall.recipe import Recipe
from squadron.benchmark.recall.report_render import ReportData, ReportRow, render_text
from squadron.benchmark.recall.scoring import recipe_outputs
from squadron.benchmark.recall.scoring_metrics import row_metrics
from squadron.benchmark.recall.scoring_paired import paired_lines
from squadron.benchmark.recall.scoring_select import ImportOnlyResolver
from squadron.core.models import Effort
from squadron.metrology.recall_case_models import RecallCaseSet
from squadron.metrology.recall_label_models import HitVerdict
from squadron.metrology.recall_run_models import RecallRun, StageEntry
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
