"""The kept-findings rule over a reviewer's findings and its comb chain (slice 434, D5).

A CONCERN or FAIL finding is **kept** when every comb in the chain decided KEEP, or left
it ``UNDECIDED``. An undecided finding is never dropped and is not sent to the next comb.
NOTE and PASS findings are never combed. Pure functions: no I/O, no model call.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from squadron.metrology.recall_run_models import CombDecision, CombVerdict, RecallFinding
from squadron.recipes.comb_call import finding_id_at
from squadron.review.models import SCORED_SEVERITIES


@dataclass(frozen=True)
class CombInput:
    """A reviewer's findings split into what a chain combs and what it never sees."""

    scored: tuple[RecallFinding, ...]
    unscored: tuple[RecallFinding, ...]


@dataclass(frozen=True)
class CombStep:
    """One comb's effect on its input: KEEP continues, DROP stops, UNDECIDED is kept."""

    kept: tuple[RecallFinding, ...]
    dropped: tuple[RecallFinding, ...]
    undecided: tuple[RecallFinding, ...]


def comb_input(findings: Sequence[RecallFinding]) -> CombInput:
    """CONCERN/FAIL findings start the chain; NOTE/PASS are returned separately."""
    scored = tuple(f for f in findings if f.severity in SCORED_SEVERITIES)
    unscored = tuple(f for f in findings if f.severity not in SCORED_SEVERITIES)
    return CombInput(scored=scored, unscored=unscored)


def decisions_by_finding(
    findings: Sequence[RecallFinding], positional: Mapping[str, CombDecision]
) -> dict[str, CombDecision]:
    """Map a comb's decisions, keyed by the ``F1..Fn`` it was shown, to the findings' ids."""
    return {
        finding.finding_id: positional[finding_id_at(index)]
        for index, finding in enumerate(findings)
        if finding_id_at(index) in positional
    }


def apply_comb(findings: Sequence[RecallFinding], decisions: Mapping[str, CombDecision]) -> CombStep:
    """Split one comb's input by its decisions (keyed by finding id); no decision is UNDECIDED."""
    kept: list[RecallFinding] = []
    dropped: list[RecallFinding] = []
    undecided: list[RecallFinding] = []
    for finding in findings:
        decision = decisions.get(finding.finding_id)
        verdict = decision.verdict if decision is not None else CombVerdict.UNDECIDED
        match verdict:
            case CombVerdict.KEEP:
                kept.append(finding)
            case CombVerdict.DROP:
                dropped.append(finding)
            case CombVerdict.UNDECIDED:
                undecided.append(finding)
    return CombStep(kept=tuple(kept), dropped=tuple(dropped), undecided=tuple(undecided))


def pass_through(findings: Sequence[RecallFinding]) -> CombStep:
    """A failed comb: its whole input continues uncombed, as if kept."""
    return CombStep(kept=tuple(findings), dropped=(), undecided=())


def chain_result(
    initial: Sequence[RecallFinding], steps: Sequence[CombStep]
) -> tuple[RecallFinding, ...]:
    """The kept set after the chain, in the reviewer's order: everything the last comb still
    kept plus every finding any comb left undecided. No steps keeps the whole input."""
    if not steps:
        return tuple(initial)
    kept_ids = {f.finding_id for f in steps[-1].kept}
    kept_ids.update(f.finding_id for step in steps for f in step.undecided)
    return tuple(f for f in initial if f.finding_id in kept_ids)
