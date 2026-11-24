"""Hand-built cases, entries and runs for the scoring tests (slice 430)."""

from __future__ import annotations

from squadron.benchmark.recall.scoring_select import StageIdentity
from squadron.core.finding_categories import ReviewCategory
from squadron.core.models import Effort
from squadron.metrology.recall_case_models import RealBugCase
from squadron.metrology.recall_run_models import (
    CombDecision,
    CombVerdict,
    RecallFinding,
    RecallLeakVerdict,
    RecallRun,
    StageConfig,
    StageEntry,
    StageKind,
    StageOutcome,
    StageUsage,
    chain_key,
    comb_slot,
    content_key,
)
from squadron.recipes.recipe import ReviewerOptions
from tests.benchmark.recall.support import FIXED_NOW, case_fields, make_bug

IMPORT_SOURCE = "import:20261112-grid2"


def make_case(
    name: str = "demo-1", bug_files: tuple[str, ...] = ("src/a.py", "src/b.py")
) -> RealBugCase:
    bugs = tuple(make_bug(f"B{i + 1}", file) for i, file in enumerate(bug_files))
    # The name is not part of the case id, so vary head to keep cases distinct.
    head = (name + "h" * 40)[:40]
    return RealBugCase.build(**case_fields(name=name, bugs=bugs, head=head))


def finding(
    index: int,
    location: str | None,
    severity: str = "CONCERN",
    text: str = "",
    category: ReviewCategory | None = None,
) -> RecallFinding:
    title = f"finding {index} {text}"
    return RecallFinding(
        finding_id=f"F{index}",
        content_key=content_key(location, title, "d"),
        severity=severity,
        category=category,
        location=location,
        title=title,
        description="d",
    )


def config(model: str, template: str = "code") -> StageConfig:
    return StageConfig(
        model=model, profile="p", template_hash=template, tool_use=True, max_output_tokens=None
    )


def review(
    alias: str,
    findings: tuple[RecallFinding, ...],
    *,
    model: str | None = None,
    source: str = IMPORT_SOURCE,
    effort_sent: Effort | None = None,
    outcome: StageOutcome = StageOutcome.OK,
    leak: RecallLeakVerdict = RecallLeakVerdict.NOT_SCANNED,
    cost: float | None = 0.5,
    case_set: str = "s@v1",
) -> StageEntry:
    return StageEntry(
        kind=StageKind.REVIEW,
        config=config(model or alias),
        effort_configured=None,
        effort_sent=effort_sent,
        findings=findings,
        usage=StageUsage(cost_usd=cost),
        outcome=outcome,
        leak=leak,
        source=source,
        case_set=case_set,
        alias=alias,
        created=FIXED_NOW,
    )


def comb(
    alias: str,
    decisions: dict[str, CombVerdict],
    *,
    source: str = IMPORT_SOURCE,
    outcome: StageOutcome = StageOutcome.OK,
    template: str | None = None,
) -> StageEntry:
    return StageEntry(
        kind=StageKind.COMB,
        config=config(alias, template or f"comb#{alias}"),
        effort_configured=None,
        effort_sent=None,
        decisions={fid: CombDecision(verdict=v) for fid, v in decisions.items()},
        usage=StageUsage(cost_usd=0.1),
        outcome=outcome,
        leak=RecallLeakVerdict.NOT_SCANNED,
        source=source,
        case_set="s@v1",
        alias=alias,
        created=FIXED_NOW,
    )


def make_run(case: RealBugCase, run_index: int, *reviews: StageEntry) -> RecallRun:
    return RecallRun(
        case_id=case.case_id, run_index=run_index, reviews={r.entry_key: r for r in reviews}
    )


def add_chain(run: RecallRun, review_entry: StageEntry, *combs: StageEntry) -> None:
    keys: list[str] = []
    for entry in combs:
        keys.append(entry.entry_key)
        run.combs[comb_slot(review_entry.entry_key, chain_key(keys))] = entry


class StubResolver:
    """Resolves aliases to fixed identities; a reviewer with options by ``(alias, options)``."""

    def __init__(
        self,
        identities: dict[str, StageIdentity],
        with_options: dict[tuple[str, ReviewerOptions], StageIdentity] | None = None,
    ) -> None:
        self._identities = identities
        self._with_options = with_options or {}

    def resolve(
        self, alias: str, stage_kind: StageKind, options: ReviewerOptions | None = None
    ) -> StageIdentity | None:
        if options is not None:
            return self._with_options.get((alias, options))
        return self._identities.get(alias)
