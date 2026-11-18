"""Per-row metrics: recall bounds, counts, real share, cost, leaks (slice 430 D2, D3, D5). Pure.

A pool row is the mean of its members' metrics, each member scored as a single reviewer
over the same (case, run) pairs: the expected value of a random pick, with no sampling.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field

from squadron.benchmark.recall.label_precedence import ResolvedLabels
from squadron.benchmark.recall.scoring import PairOutput, ReviewerOutput, RowOutputs
from squadron.benchmark.recall.scoring_pair import PairScore, score_pair
from squadron.metrology.recall_label_models import FindingGrade
from squadron.metrology.recall_run_models import StageEntry

LabelsByCase = dict[str, ResolvedLabels]


@dataclass(frozen=True)
class Bounds:
    low: float
    high: float

    @property
    def exact(self) -> bool:
        return self.low == self.high


@dataclass
class RowMetrics:
    cases: int = 0
    runs: int = 0
    pairs: int = 0
    bug_hits: Bounds = Bounds(0, 0)
    #: bugs × runs, summed over scored pairs.
    bug_slots: int = 0
    bugs_found: Bounds = Bounds(0, 0)
    bugs_total: int = 0
    runs_with_hit: Bounds = Bounds(0, 0)
    adjacent: float = 0
    undecided: float = 0
    findings_per_run: float = 0
    matched_nothing: float = 0
    real: float = 0
    graded: float = 0
    passes: tuple[str, ...] = ()
    person_checked: float = 0
    person_agree: float = 0
    cost_per_run: float | None = None
    cost_bases: tuple[str, ...] = ()
    leaks: Counter[str] = field(default_factory=Counter[str])
    other_set_entries: int = 0
    #: Bug-hits low/high and bug slots per ``original_review`` value.
    by_original_review: dict[str, tuple[Bounds, int]] = field(
        default_factory=dict[str, tuple[Bounds, int]]
    )

    @property
    def recall(self) -> Bounds:
        if not self.bug_slots:
            return Bounds(0, 0)
        return Bounds(self.bug_hits.low / self.bug_slots, self.bug_hits.high / self.bug_slots)

    @property
    def real_share(self) -> float | None:
        return None if not self.graded else self.real / self.graded


def row_metrics(row: RowOutputs, labels: LabelsByCase, set_label: str) -> RowMetrics:
    """The metrics of *row*; *set_label* (``name@vN``) is the report's set version."""
    if row.recipe.pool and row.pairs:
        members = [
            _metrics(
                [_pair_score(pair, (pair.reviewers[i],), labels) for pair in row.pairs],
                [entry for pair in row.pairs for entry in pair.reviewers[i].entries],
            )
            for i in range(len(row.recipe.reviewers))
        ]
        metrics = mean_metrics(members)
    else:
        metrics = _metrics(
            [_pair_score(pair, pair.reviewers, labels) for pair in row.pairs],
            [entry for pair in row.pairs for entry in pair.entries],
        )
    entries = [entry for pair in row.pairs for entry in pair.entries]
    metrics.leaks = Counter(entry.leak.value for entry in entries)
    metrics.other_set_entries = sum(entry.case_set != set_label for entry in entries)
    return metrics


def per_case_scores(row: RowOutputs, labels: LabelsByCase) -> dict[str, list[list[PairScore]]]:
    """case id -> per member (one entry unless pool) -> that case's pair scores."""
    members = range(len(row.recipe.reviewers)) if row.recipe.pool else [None]
    found: dict[str, list[list[PairScore]]] = {}
    for pair in row.pairs:
        per_member = found.setdefault(pair.case.case_id, [[] for _ in members])
        for slot, member in enumerate(members):
            reviewers = pair.reviewers if member is None else (pair.reviewers[member],)
            per_member[slot].append(_pair_score(pair, reviewers, labels))
    return found


def _pair_score(
    pair: PairOutput, reviewers: tuple[ReviewerOutput, ...], labels: LabelsByCase
) -> PairScore:
    return score_pair(
        pair.case, pair.run_index, reviewers, labels.get(pair.case.case_id, ResolvedLabels())
    )


def _metrics(scores: list[PairScore], entries: list[StageEntry]) -> RowMetrics:
    if not scores:
        return RowMetrics()
    found_low = {(s.case.case_id, b) for s in scores for b in s.hit_low}
    found_high = {(s.case.case_id, b) for s in scores for b in s.hit_high}
    graded = [grade for s in scores for grade in s.grades]
    cost, bases = _cost(entries, len(scores))
    return RowMetrics(
        cases=len({s.case.case_id for s in scores}),
        runs=len({s.run_index for s in scores}),
        pairs=len(scores),
        bug_hits=Bounds(sum(len(s.hit_low) for s in scores), sum(len(s.hit_high) for s in scores)),
        bug_slots=sum(s.bug_count for s in scores),
        bugs_found=Bounds(len(found_low), len(found_high)),
        bugs_total=len({(s.case.case_id, b.id) for s in scores for b in s.case.bugs}),
        runs_with_hit=Bounds(
            sum(bool(s.hit_low) for s in scores), sum(bool(s.hit_high) for s in scores)
        ),
        adjacent=sum(s.adjacent for s in scores),
        undecided=sum(s.undecided for s in scores),
        findings_per_run=sum(s.findings for s in scores) / len(scores),
        matched_nothing=sum(s.matched_nothing for s in scores),
        real=sum(grade is FindingGrade.REAL for grade, _ in graded),
        graded=len(graded),
        passes=tuple(sorted({labeler for _, labeler in graded})),
        person_checked=sum(s.person_checked for s in scores),
        person_agree=sum(s.person_agree for s in scores),
        cost_per_run=cost,
        cost_bases=bases,
        by_original_review=_by_original_review(scores),
    )


def _by_original_review(scores: list[PairScore]) -> dict[str, tuple[Bounds, int]]:
    split: dict[str, tuple[Bounds, int]] = {}
    for s in scores:
        for bug in s.case.bugs:
            key = bug.original_review.value
            bounds, slots = split.get(key, (Bounds(0, 0), 0))
            split[key] = (
                Bounds(bounds.low + (bug.id in s.hit_low), bounds.high + (bug.id in s.hit_high)),
                slots + 1,
            )
    return split


def _cost(entries: list[StageEntry], pairs: int) -> tuple[float | None, tuple[str, ...]]:
    """Mean cost per (case, run); ``None`` when any entry has no recorded cost."""
    costs = [entry.usage.cost_usd for entry in entries]
    bases = tuple(
        sorted({e.usage.cost_basis.value if e.usage.cost_basis else "unknown" for e in entries})
    )
    if any(cost is None for cost in costs):
        return None, bases
    return sum(cost for cost in costs if cost is not None) / pairs, bases


def mean_metrics(members: list[RowMetrics]) -> RowMetrics:
    """The mean of *members*, which were scored over the same pairs (a pool's expected pick)."""
    if not members:
        return RowMetrics()
    n = len(members)
    first = members[0]

    def avg(get: Callable[[RowMetrics], float]) -> float:
        return sum(get(m) for m in members) / n

    def avg_bounds(get: Callable[[RowMetrics], Bounds]) -> Bounds:
        return Bounds(avg(lambda m: get(m).low), avg(lambda m: get(m).high))

    costs = [m.cost_per_run for m in members]
    return RowMetrics(
        cases=first.cases,
        runs=first.runs,
        pairs=first.pairs,
        bug_hits=avg_bounds(lambda m: m.bug_hits),
        bug_slots=first.bug_slots,
        bugs_found=avg_bounds(lambda m: m.bugs_found),
        bugs_total=first.bugs_total,
        runs_with_hit=avg_bounds(lambda m: m.runs_with_hit),
        adjacent=avg(lambda m: m.adjacent),
        undecided=avg(lambda m: m.undecided),
        findings_per_run=avg(lambda m: m.findings_per_run),
        matched_nothing=avg(lambda m: m.matched_nothing),
        real=avg(lambda m: m.real),
        graded=avg(lambda m: m.graded),
        passes=tuple(sorted({p for m in members for p in m.passes})),
        person_checked=avg(lambda m: m.person_checked),
        person_agree=avg(lambda m: m.person_agree),
        cost_per_run=None if None in costs else sum(c for c in costs if c is not None) / n,
        cost_bases=tuple(sorted({b for m in members for b in m.cost_bases})),
        by_original_review=_mean_split([m.by_original_review for m in members]),
    )


def _mean_split(splits: list[dict[str, tuple[Bounds, int]]]) -> dict[str, tuple[Bounds, int]]:
    n = len(splits)
    merged: dict[str, tuple[Bounds, int]] = {}
    for key, (_, slots) in splits[0].items():
        low = sum(split[key][0].low for split in splits) / n
        high = sum(split[key][0].high for split in splits) / n
        merged[key] = (Bounds(low, high), slots)
    return merged
