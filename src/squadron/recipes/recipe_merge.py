"""Combine a recipe's stages into one review result (slice 434, D5, D6).

Findings: reviewer 1's kept, reviewer 2's kept, then the NOTE/PASS findings in reviewer
order; each names its reviewer (and a failed comb it passed through) in its description.
Dropped findings appear nowhere: the reviser reads the review file. The verdict is
``verdict_from_findings`` over the merged findings, except that an incomplete recipe
cannot pass: incomplete with nothing kept is UNKNOWN, incomplete with a CONCERN/FAIL
kept is FAIL.
"""

from __future__ import annotations

import dataclasses
from collections import Counter
from collections.abc import Iterable

from squadron.core.tool_calls import ToolCallRecord
from squadron.metrology.recall_run_models import CombVerdict, RecallFinding, StageKind, StageOutcome
from squadron.recipes.recipe_outcome import (
    RecipeOutcome,
    RecipeStageResult,
    ReviewerOutcome,
    stage_totals,
)
from squadron.review.models import (
    RecipeReviewInfo,
    ReviewFinding,
    ReviewResult,
    Verdict,
    VerdictSource,
)
from squadron.review.parsers import verdict_from_findings

#: The heading of the stage section in the review file.
RECIPE_SECTION_HEADING = "## Recipe"
INCOMPLETE_FAIL_NOTE = (
    "The verdict is FAIL because the recipe is incomplete (a stage failed) while findings "
    "were kept; an incomplete recipe cannot pass."
)
INCOMPLETE_UNKNOWN_NOTE = (
    "The verdict is UNKNOWN because the recipe is incomplete (a stage failed) and no "
    "finding was kept; an incomplete recipe cannot pass."
)
_NO_VALUE = "—"


def _marked(finding: ReviewFinding, reviewer: str, failed_comb: str | None) -> ReviewFinding:
    mark = f"Reviewer: {reviewer}"
    if failed_comb is not None:
        mark += f" (not combed: {failed_comb} failed)"
    return dataclasses.replace(finding, description=f"{finding.description}\n\n{mark}")


def _from(reviewer: ReviewerOutcome, findings: Iterable[RecallFinding]) -> list[ReviewFinding]:
    return [
        _marked(reviewer.source[f.finding_id], reviewer.reviewer, reviewer.not_combed.get(f.finding_id))
        for f in findings
    ]


def merged_findings(outcome: RecipeOutcome) -> list[ReviewFinding]:
    """Kept findings per reviewer in recipe order, then NOTE/PASS in the same order."""
    kept = [f for r in outcome.reviewers for f in _from(r, r.kept)]
    return kept + [f for r in outcome.reviewers for f in _from(r, r.uncombed)]


def merged_verdict(findings: list[ReviewFinding], complete: bool) -> Verdict:
    """The existing findings rule; an incomplete recipe gives UNKNOWN or FAIL, never PASS."""
    verdict = verdict_from_findings(findings)
    if complete:
        return verdict
    return Verdict.UNKNOWN if verdict is Verdict.PASS else Verdict.FAIL


def _counts(stage: RecipeStageResult) -> str:
    if stage.kind is StageKind.REVIEW:
        return f"{len(stage.findings)} findings"
    if stage.not_combed:
        return f"{len(stage.not_combed)} not combed"
    tally = Counter(d.verdict for d in stage.decisions.values())
    return (
        f"kept {tally[CombVerdict.KEEP]} / dropped {tally[CombVerdict.DROP]} / "
        f"undecided {tally[CombVerdict.UNDECIDED]}"
    )


def _answering_model(stage: RecipeStageResult) -> str:
    result = stage.result
    if result is None:
        return _NO_VALUE
    if result.answering_models:
        return result.answering_models[-1]
    return result.model or _NO_VALUE


def _cost(stage: RecipeStageResult) -> str:
    if not stage.made_call:
        return _NO_VALUE
    cost = stage.usage.cost_usd
    return f"${cost:.4f}" if cost is not None else "unpriced"


def render_stage_section(outcome: RecipeOutcome, recipe_name: str, verdict: Verdict) -> str:
    """The review file's "Recipe" section: one row per stage, then failure reasons."""
    lines = [
        RECIPE_SECTION_HEADING,
        "",
        f"Recipe `{recipe_name}`; complete: {'yes' if outcome.complete else 'no'}.",
        "",
        "| Stage | Kind | Alias | Answering model | Outcome | Findings | Cost |",
        "|---|---|---|---|---|---|---|",
    ]
    for stage in outcome.stages:
        cells = (
            stage.label,
            stage.kind.value,
            stage.alias,
            _answering_model(stage),
            stage.outcome.value,
            _counts(stage),
            _cost(stage),
        )
        lines.append("| " + " | ".join(cells) + " |")
    failed = [s for s in outcome.stages if s.outcome is not StageOutcome.OK]
    if failed:
        lines.append("")
        lines.extend(f"- Failed stage {s.label}: {s.reason}" for s in failed)
    if not outcome.complete:
        lines.append("")
        lines.append(INCOMPLETE_FAIL_NOTE if verdict is Verdict.FAIL else INCOMPLETE_UNKNOWN_NOTE)
    return "\n".join(lines)


def _summary(verdict: Verdict, section: str, findings: list[ReviewFinding]) -> str:
    body = [f"## Summary\n\n{verdict.value}", section, "## Findings"]
    body.extend(f"### [{f.severity.value}] {f.title}\n\n{f.description}" for f in findings)
    return "\n\n".join(body)


def _stage_tool_calls(results: list[ReviewResult]) -> list[ToolCallRecord] | None:
    """Every stage's tool calls in stage order (#382); None unless every stage reported its own."""
    if not results or any(result.tool_calls is None for result in results):
        return None
    return [record for result in results for record in result.tool_calls or []]


def merge_recipe(
    outcome: RecipeOutcome, recipe_name: str, template_name: str, input_files: dict[str, str]
) -> ReviewResult:
    """One ``ReviewResult`` for the whole recipe: kept findings, verdict, summed usage."""
    findings = merged_findings(outcome)
    verdict = merged_verdict(findings, outcome.complete)
    section = render_stage_section(outcome, recipe_name, verdict)
    totals = stage_totals(outcome.stages)
    results = [stage.result for stage in outcome.stages if stage.result is not None]
    return ReviewResult(
        verdict=verdict,
        findings=findings,
        raw_output=_summary(verdict, section, findings),
        template_name=template_name,
        input_files=input_files,
        model=recipe_name,
        verdict_source=VerdictSource.DERIVED,
        cost_usd=totals.cost_usd,
        duration_seconds=totals.duration_s,
        turns=totals.turns,
        tool_calls_made=totals.tool_calls,
        tool_calls=_stage_tool_calls(results),
        injected_files=next((r.injected_files for r in results if r.injected_files is not None), None),
        usage=totals.tokens,
        recipe=RecipeReviewInfo(name=recipe_name, complete=outcome.complete, stage_section=section),
    )
