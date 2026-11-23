"""The real-work table of ``sq benchmark recall report --real-work`` (slice 434, D10).

One row per recipe name, recipe hash and planned stage configs. The key comes from the plan,
so a failed reviewer, a skipped comb chain, an empty-input comb or an aborted review lands
in the same row as a complete review of the same configuration and counts as Incomplete.
Real reviews have no known bugs: the table has counts and cost only.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from squadron.core.finding_categories import ReviewCategory
from squadron.core.models import Effort
from squadron.metrology.recall_run_models import CombVerdict, StageKind, StageOutcome
from squadron.metrology.recipe_review_models import RecipeReview, RecipeStage
from squadron.recipes.kept_findings import split_by_category
from squadron.review.models import SCORED_SEVERITIES, Verdict

COLUMNS = (
    "Recipe", "Reviews", "Incomplete (aborted)", "Raw findings/review", "Not gating/review",
    "Kept/review", "Dropped/review", "Undecided/review", "Verdicts", "Cost/review (unpriced)",
)  # fmt: skip
EFFORT_DIFFERS = "effort differs"
CONFIG_DIFFERS = "config differs"
_VERDICT_ORDER = (Verdict.PASS, Verdict.CONCERNS, Verdict.FAIL, Verdict.UNKNOWN)


@dataclass(frozen=True)
class ChainCounts:
    """One record's CONCERN/FAIL findings before combs and their fate after the chain."""

    raw: int
    kept: int
    dropped: int
    undecided: int
    #: Findings the recipe's category filter left out (437 D8); not in kept, dropped or undecided.
    not_gating: int = 0


@dataclass
class RealWorkRow:
    recipe: str
    recipe_hash: str
    planned_keys: tuple[str, ...]
    records: list[RecipeReview] = field(default_factory=list[RecipeReview])
    flags: list[str] = field(default_factory=list[str])


def _reviewer_counts(
    review: RecipeStage,
    combs: Sequence[RecipeStage],
    keep: tuple[ReviewCategory, ...] | None,
) -> ChainCounts:
    """Fate of one reviewer's scored findings: not gating by the filter, else DROP stops,
    UNDECIDED is kept and stops."""
    scored = [f for f in review.findings if f.severity in SCORED_SEVERITIES]
    gating, not_gating = split_by_category(scored, keep)
    status = {f.finding_id: "kept" for f in gating}
    for comb in combs:
        for finding_id, decision in comb.decisions.items():
            if status.get(finding_id) != "kept":
                continue
            if decision.verdict is CombVerdict.DROP:
                status[finding_id] = "dropped"
            elif decision.verdict is CombVerdict.UNDECIDED:
                status[finding_id] = "undecided"
    tally = Counter(status.values())
    undecided = tally["undecided"]
    # Kept has D5's one meaning: every comb decided KEEP, or left it undecided.
    return ChainCounts(
        len(scored), tally["kept"] + undecided, tally["dropped"], undecided, len(not_gating)
    )


def chain_counts(record: RecipeReview) -> ChainCounts:
    """Summed over reviewers; a reviewer whose review stage failed contributes nothing."""
    totals = ChainCounts(0, 0, 0, 0, 0)
    for review in record.stages:
        if review.kind is not StageKind.REVIEW or review.outcome is not StageOutcome.OK:
            continue
        combs = [s for s in record.stages if s.kind is StageKind.COMB and s.reviewer == review.reviewer]
        one = _reviewer_counts(review, combs, record.keep_categories)
        totals = ChainCounts(
            totals.raw + one.raw,
            totals.kept + one.kept,
            totals.dropped + one.dropped,
            totals.undecided + one.undecided,
            totals.not_gating + one.not_gating,
        )
    return totals


def record_cost(record: RecipeReview) -> tuple[float | None, bool]:
    """(sum of known stage costs, whether any stage that made a call was unpriced)."""
    called = [s for s in record.stages if s.made_call]
    known = [s.usage.cost_usd for s in called if s.usage.cost_usd is not None]
    unpriced = any(s.usage.cost_usd is None for s in called)
    return (sum(known) if known else None), unpriced


def _effort_differs(records: Iterable[RecipeReview]) -> bool:
    sent: dict[str, set[Effort | None]] = defaultdict(set)
    for record in records:
        for stage in record.stages:
            if stage.raw_ref is not None:  # only stages whose call returned sent anything
                sent[stage.alias].add(stage.effort_sent)
    return any(len(efforts) > 1 for efforts in sent.values())


def build_rows(records: Iterable[RecipeReview], recipe_filter: Sequence[str] = ()) -> list[RealWorkRow]:
    """Group records into rows by recipe, recipe hash and planned configs; flag rows."""
    rows: dict[tuple[str, str, tuple[str, ...]], RealWorkRow] = {}
    for record in records:
        if recipe_filter and record.recipe not in recipe_filter:
            continue
        planned = tuple(config.config_key for config in record.planned)
        row = rows.setdefault(
            (record.recipe, record.recipe_hash, planned),
            RealWorkRow(record.recipe, record.recipe_hash, planned),
        )
        row.records.append(record)
    names = Counter(row.recipe for row in rows.values())
    for row in rows.values():
        if _effort_differs(row.records):
            row.flags.append(EFFORT_DIFFERS)
        if names[row.recipe] > 1:
            row.flags.append(CONFIG_DIFFERS)
    return sorted(rows.values(), key=lambda row: (row.recipe, row.records[0].created))


def _per_review(total: int, reviews: int) -> str:
    return f"{total / reviews:.1f}"


def _row_cells(row: RealWorkRow) -> list[str]:
    reviews = len(row.records)
    counts = [chain_counts(record) for record in row.records]
    incomplete = sum(1 for r in row.records if not r.complete)
    aborted = sum(1 for r in row.records if r.aborted is not None)
    verdicts = Counter(r.verdict for r in row.records)
    costs = [record_cost(r) for r in row.records]
    known = [cost for cost, _ in costs if cost is not None]
    unpriced = sum(1 for _, flag in costs if flag)
    mean = f"${sum(known) / len(known):.2f}" if known else "unpriced"
    label = f"{row.recipe} [{row.recipe_hash[:8]}]"
    if row.flags:
        label += f" ({', '.join(row.flags)})"
    return [
        label,
        str(reviews),
        f"{incomplete} ({aborted})",
        _per_review(sum(c.raw for c in counts), reviews),
        _per_review(sum(c.not_gating for c in counts), reviews),
        _per_review(sum(c.kept for c in counts), reviews),
        _per_review(sum(c.dropped for c in counts), reviews),
        _per_review(sum(c.undecided for c in counts), reviews),
        " ".join(f"{v.value} {verdicts[v]}" for v in _VERDICT_ORDER),
        f"{mean} ({unpriced})",
    ]


def render_real_work(rows: Sequence[RealWorkRow]) -> str:
    """The real-work table, in the recall report's markdown style."""
    if not rows:
        return "Real work: no recipe_review records for this project."
    lines = [
        f"Real work: {sum(len(r.records) for r in rows)} recipe reviews in {len(rows)} rows.",
        "Kept counts undecided findings too (D5); Incomplete counts aborted reviews too.",
        "",
        "| " + " | ".join(COLUMNS) + " |",
        "|" + "---|" * len(COLUMNS),
    ]
    lines += ["| " + " | ".join(_row_cells(row)) + " |" for row in rows]
    return "\n".join(lines)
