"""The ``report --json`` document: the schema slice 433 reads (slice 430 Integration Points)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from squadron.benchmark.recall.report_render import ReportData, ReportRow
from squadron.benchmark.recall.scoring_metrics import Bounds
from squadron.benchmark.recall.scoring_paired import PairedLine

REPORT_CATEGORY = "code-review"


class BoundsJson(BaseModel):
    model_config = ConfigDict(frozen=True)

    low: float
    high: float


class RowJson(BaseModel):
    model_config = ConfigDict(frozen=True)

    label: str
    key: str
    recipe: str
    flagged: bool
    source: str
    cases: int
    runs: int
    pairs: int
    bug_hits: BoundsJson
    bug_slots: int
    recall: BoundsJson
    bugs_found: BoundsJson
    bugs_total: int
    runs_with_hit: BoundsJson
    adjacent: float
    undecided: float
    findings_per_run: float
    matched_nothing: float
    real_share: float | None
    graded: float
    passes: list[str]
    person_checked: float
    person_agree: float
    cost_per_run: float | None
    cost_bases: list[str]
    leaks: dict[str, int]
    dropped: dict[str, int]
    left_out: list[str]
    other_set_entries: int


class PairedJson(BaseModel):
    model_config = ConfigDict(frozen=True)

    a: str
    b: str
    metric: str
    n: int
    mean: float
    low: float | None
    high: float | None
    verdict: str
    left_out_undecided: int


class RecallReportJson(BaseModel):
    model_config = ConfigDict(frozen=True)

    category: str
    case_set: str
    case_set_version: int
    n_cases: int
    known_bugs: int
    run_indexes: list[int]
    newest_entry: datetime | None
    rows: list[RowJson]
    paired: list[PairedJson]


def _bounds(value: Bounds) -> BoundsJson:
    return BoundsJson(low=value.low, high=value.high)


def _row(row: ReportRow) -> RowJson:
    m, o = row.metrics, row.outputs
    return RowJson(
        label=o.label,
        key=o.key,
        recipe=o.recipe.name,
        flagged=o.flagged,
        source=o.source_tag,
        cases=m.cases,
        runs=m.runs,
        pairs=m.pairs,
        bug_hits=_bounds(m.bug_hits),
        bug_slots=m.bug_slots,
        recall=_bounds(m.recall),
        bugs_found=_bounds(m.bugs_found),
        bugs_total=m.bugs_total,
        runs_with_hit=_bounds(m.runs_with_hit),
        adjacent=m.adjacent,
        undecided=m.undecided,
        findings_per_run=m.findings_per_run,
        matched_nothing=m.matched_nothing,
        real_share=m.real_share,
        graded=m.graded,
        passes=list(m.passes),
        person_checked=m.person_checked,
        person_agree=m.person_agree,
        cost_per_run=m.cost_per_run,
        cost_bases=list(m.cost_bases),
        leaks=dict(m.leaks),
        dropped=dict(o.dropped),
        left_out=[f"{case} run {run}" for case, run in o.left_out],
        other_set_entries=m.other_set_entries,
    )


def _paired(line: PairedLine) -> PairedJson:
    c = line.comparison
    return PairedJson(
        a=line.label_a,
        b=line.label_b,
        metric=line.metric.value,
        n=c.n,
        mean=c.mean,
        low=c.low,
        high=c.high,
        verdict=c.verdict.value,
        left_out_undecided=line.left_out_undecided,
    )


def report_json(data: ReportData) -> RecallReportJson:
    return RecallReportJson(
        category=REPORT_CATEGORY,
        case_set=data.case_set.name,
        case_set_version=data.case_set.version,
        n_cases=len(data.case_set.case_ids),
        known_bugs=data.known_bugs,
        run_indexes=data.run_indexes,
        newest_entry=data.newest_entry,
        rows=[_row(row) for row in data.rows],
        paired=[_paired(line) for line in data.paired],
    )
