"""One comb call (slice 430 D6; moved to ``recipes/`` in slice 434, D4).

The comb's input findings are rendered ``F1..Fn`` by position, in the hand-run
``comb.py render`` format, and sent with the ``comb`` template through the injected review
call. ``sq benchmark recall _stage`` and production recipe reviews both call
``run_comb_stage``.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from squadron.core.models import Effort
from squadron.metrology.recall_run_models import RecallFinding
from squadron.recipes.decisions import DecisionParse, parse_decisions
from squadron.review.models import ReviewResult
from squadron.review.templates import ReviewTemplate

#: The comb's tools: squadron's builtins, which refuse paths outside the working directory.
COMB_ALLOWED_TOOLS = ("read_file", "list_files", "grep")
FINDING_ID_PREFIX = "F"

ReviewCall = Callable[..., Awaitable[ReviewResult]]


def finding_id_at(index: int) -> str:
    """The positional finding id of the finding at *index* (0-based) in ``findings``."""
    return f"{FINDING_ID_PREFIX}{index + 1}"


@dataclass(frozen=True)
class StageModel:
    """The resolved alias: what the comb call is sent with."""

    alias: str
    model: str
    profile: str
    effort: Effort | None
    max_output_tokens: int | None
    #: The alias's ``tool_use``: ``False`` withholds the comb's tools, as for ``sq review``.
    allows_tools: bool


def render_findings(findings: list[RecallFinding]) -> str:
    """``### F<n> [<severity>] <title>`` blocks, F1 first: the ``comb.py render`` format."""
    blocks = [
        f"### {finding_id_at(i)} [{f.severity}] {f.title}\nLocation: {f.location}\n\n{f.description}"
        for i, f in enumerate(findings)
    ]
    return "\n\n".join(blocks)


@dataclass(frozen=True)
class CombCallResult:
    """One comb call's review result and its parsed decisions (keyed ``F1..Fn``)."""

    result: ReviewResult
    parsed: DecisionParse


async def call_comb(
    *,
    template: ReviewTemplate,
    findings: list[RecallFinding],
    changed: str,
    cwd: Path,
    model: StageModel,
    review_call: ReviewCall,
) -> CombCallResult:
    """Send *findings* to the comb with read-only tools; parse its decision lines."""
    inputs = {"findings": render_findings(findings), "changed_files": changed, "cwd": str(cwd)}
    result = await review_call(
        template,
        inputs,
        profile=model.profile,
        model=model.model,
        allowed_tools=list(COMB_ALLOWED_TOOLS),
        model_allows_tools=model.allows_tools,
        effort=model.effort,
        alias=model.alias,
        max_output_tokens=model.max_output_tokens,
    )
    ids = [finding_id_at(index) for index in range(len(findings))]
    return CombCallResult(result=result, parsed=parse_decisions(result.raw_output, ids))


CombCall = Callable[..., Awaitable[CombCallResult]]


async def run_comb_stage(
    *,
    template: ReviewTemplate,
    findings: list[RecallFinding],
    changed: str,
    cwd: Path,
    model: StageModel,
    review_call: ReviewCall,
) -> dict[str, Any]:
    """Call the model; the output document (raw text, decisions, usage) once it returns."""
    call = await call_comb(
        template=template,
        findings=findings,
        changed=changed,
        cwd=cwd,
        model=model,
        review_call=review_call,
    )
    return {
        **call.result.to_dict(),
        "raw_output": call.result.raw_output,
        "decisions": {fid: [d.verdict.value, d.reason] for fid, d in call.parsed.decisions.items()},
    }
