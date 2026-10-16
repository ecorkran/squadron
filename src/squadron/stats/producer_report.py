"""The ``sq stats producers`` report core: observed producer effectiveness (slice 176 D8).

Read-only and observational: configs saw different slices, so slice difficulty is a
confound, and prompt-template revisions are pooled. Controlled comparison is the replay
follow-on's job. Each row carries its n; a row below the evidence floor is marked and
sorted after the rest.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass
from enum import StrEnum

from squadron.core.usage import UsageRecord
from squadron.pipeline.executor import ExecutionStatus
from squadron.pipeline.loop_config import LoopCondition
from squadron.pipeline.state import StateManager
from squadron.pipeline.steps import StepTypeName
from squadron.review.models import Verdict
from squadron.stats.json_support import to_json_dict
from squadron.stats.producer_units import (
    PHASE_TYPES,
    ExcludedCounts,
    ProducerKey,
    ProducerUnit,
    extract_units,
)
from squadron.stats.usage_report import LLM_ACTION_TYPES, action_usage_row, usage_totals

_ACCEPTANCE = LoopCondition.REVIEW_CONCERNS_OR_BETTER


class FirstRound(StrEnum):
    """The first-round verdict buckets (D8); anything else is ``none``."""

    PASS = Verdict.PASS.value
    CONCERNS = Verdict.CONCERNS.value
    FAIL = Verdict.FAIL.value
    NONE = "none"


@dataclass(frozen=True)
class ProducerRow:
    model: str | None
    alias: str | None
    profile: str | None
    effort: str | None
    reviewer: str | None
    pipelines: tuple[str, ...]
    n: int
    below_floor: bool
    first_round: dict[str, int]  # FirstRound value -> runs
    median_revise_rounds: float
    accepted: int
    failed: int
    cost_usd: float | None  # all recorded spend of these runs' phase and loop steps
    priced: int
    llm_actions: int
    cost_per_accepted: float | None


@dataclass(frozen=True)
class PhaseSection:
    phase: str
    runs: int  # distinct pipeline runs with a unit in this phase
    rows: tuple[ProducerRow, ...]


@dataclass(frozen=True)
class ProducerReport:
    min_n: int
    phases: tuple[PhaseSection, ...]
    excluded: ExcludedCounts
    unreadable_runs: int
    rounds_unrecorded: int  # loops with several rounds but no per-round data (pre-176 runs)
    unpriced_runs: int  # units with no recorded cost at all (pre-175 runs)

    def to_json_dict(self) -> dict[str, object]:
        return to_json_dict(self)


def producer_report(
    *, phase: StepTypeName | None, state_manager: StateManager, min_n: int
) -> ProducerReport:
    """Aggregate producer configs per phase; ``phase`` of ``None`` reports both."""
    scan = state_manager.scan_runs()
    extraction = extract_units(scan.states)
    wanted = PHASE_TYPES if phase is None else (phase,)
    units = [unit for unit in extraction.units if unit.phase in wanted]
    sections = tuple(
        _section(p, [u for u in units if u.phase == p], min_n)
        for p in wanted
        if any(u.phase == p for u in units)
    )
    return ProducerReport(
        min_n=min_n,
        phases=sections,
        excluded=extraction.excluded,
        unreadable_runs=len(scan.unreadable),
        rounds_unrecorded=sum(_rounds_unrecorded(unit) for unit in units),
        unpriced_runs=sum(_unpriced(unit) for unit in units),
    )


def _section(phase: StepTypeName, units: list[ProducerUnit], min_n: int) -> PhaseSection:
    by_key: dict[ProducerKey, list[ProducerUnit]] = defaultdict(list)
    for unit in units:
        by_key[unit.key].append(unit)
    rows = [_row(key, members, min_n) for key, members in by_key.items()]
    rows.sort(key=lambda row: (row.below_floor, -row.n, row.model or ""))
    return PhaseSection(phase=phase.value, runs=len({u.run_id for u in units}), rows=tuple(rows))


def _row(key: ProducerKey, members: list[ProducerUnit], min_n: int) -> ProducerRow:
    records = [record for unit in members for record in _records(unit)[0]]
    actions = sum(_records(unit)[1] for unit in members)
    totals = usage_totals(records)
    accepted = sum(_accepted(unit) for unit in members)
    first = defaultdict(int, {bucket.value: 0 for bucket in FirstRound})
    for unit in members:
        first[_first_round(unit).value] += 1
    return ProducerRow(
        model=key.model,
        alias=next((u.alias for u in members if u.alias), None),
        profile=key.profile,
        effort=key.effort,
        reviewer=key.reviewer,
        pipelines=tuple(sorted({unit.pipeline for unit in members})),
        n=len(members),
        below_floor=len(members) < min_n,
        first_round=dict(first),
        median_revise_rounds=float(statistics.median(_revise_rounds(unit) for unit in members)),
        accepted=accepted,
        failed=sum(unit.phase_step.status == ExecutionStatus.FAILED for unit in members),
        cost_usd=totals.cost_usd,
        priced=totals.priced,
        llm_actions=actions,
        cost_per_accepted=(
            totals.cost_usd / accepted if totals.cost_usd is not None and accepted else None
        ),
    )


def _first_round(unit: ProducerUnit) -> FirstRound:
    verdict = unit.phase_step.verdict
    try:
        bucket = FirstRound(verdict)
    except ValueError:
        return FirstRound.NONE  # no review verdict, or UNKNOWN: not a verdict to count
    return bucket


def _revise_rounds(unit: ProducerUnit) -> int:
    """Loop rounds run: from the persisted rounds (D3), else the loop's own iteration."""
    loop = unit.loop_step
    if loop is None:
        return 0
    return len(loop.prior_round_results) + 1 if loop.prior_round_results else loop.iteration


def _unpriced(unit: ProducerUnit) -> bool:
    """No priced record at all: a run from before 175, or one on an unpriced model."""
    return all(record.cost_usd is None for record in _records(unit)[0])


def _rounds_unrecorded(unit: ProducerUnit) -> bool:
    loop = unit.loop_step
    return loop is not None and not loop.prior_round_results and loop.iteration > 1


def _accepted(unit: ProducerUnit) -> bool:
    """The loop ended accepted, or with no loop the first-round verdict already passes (D8)."""
    if unit.phase_step.status != ExecutionStatus.COMPLETED:
        return False
    loop = unit.loop_step
    if loop is None:
        verdict = unit.phase_step.verdict
        return verdict is not None and _ACCEPTANCE.met_by_verdict(verdict)
    if loop.status != ExecutionStatus.COMPLETED:
        return False
    # `accepted` is set when a loop exhausted its rounds but met accept_if; a loop whose
    # `until` was met ends completed on an acceptable verdict, and so does a pre-176 file.
    return loop.accepted or (loop.verdict is not None and _ACCEPTANCE.met_by_verdict(loop.verdict))


def _records(unit: ProducerUnit) -> tuple[list[UsageRecord], int]:
    """Usage records and LLM action count over the phase step and every loop round."""
    steps = [unit.phase_step.action_results]
    if unit.loop_step is not None:
        steps += [*unit.loop_step.prior_round_results, unit.loop_step.action_results]
    records: list[UsageRecord] = []
    llm_actions = 0
    for actions in steps:
        for action in actions:
            row = action_usage_row(unit.run_id, unit.phase_step.step_name, action)
            llm_actions += row.action_type in LLM_ACTION_TYPES
            if row.record is not None:
                records.append(row.record)
    return records, llm_actions
