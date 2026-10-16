"""The ``sq stats producers`` report core: observed producer effectiveness (slice 176 D8).

Read-only and observational: configs saw different slices, so slice difficulty is a
confound, and prompt-template revisions are pooled. Controlled comparison is the replay
follow-on's job. Each row carries its n; a row below the evidence floor is marked and
sorted after the rest.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import cast

from squadron.core.usage import UsageRecord
from squadron.pipeline.actions import ActionType
from squadron.pipeline.actions.prompt_identity import PROMPT_METADATA_KEY
from squadron.pipeline.executor import ExecutionStatus
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
    loop_rounds,
    phase_accepted,
    unit_usage,
)
from squadron.stats.usage_report import usage_totals


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
    units: int  # every unit reported, the denominator of prompt_identified
    prompt_identified: int  # units whose phase dispatch carries metadata["prompt"] (177 D8)
    guide_versions: int  # distinct non-None guide versions among those identities

    def to_json_dict(self) -> dict[str, object]:
        return to_json_dict(self)


def producer_report(
    *, phase: StepTypeName | None, state_manager: StateManager, min_n: int
) -> ProducerReport:
    """Aggregate producer configs per phase; ``phase`` of ``None`` reports both."""
    scan = state_manager.scan_runs()
    extraction = extract_units(scan.states)
    wanted = PHASE_TYPES if phase is None else (phase,)
    units = [_usage(unit) for unit in extraction.units if unit.phase in wanted]
    identities = [i for i in (_prompt_identity(u.unit) for u in units) if i is not None]
    sections = tuple(
        _section(p, [u for u in units if u.unit.phase == p], min_n)
        for p in wanted
        if any(u.unit.phase == p for u in units)
    )
    return ProducerReport(
        min_n=min_n,
        phases=sections,
        excluded=extraction.excluded,
        unreadable_runs=len(scan.unreadable),
        rounds_unrecorded=sum(_rounds_unrecorded(u.unit) for u in units),
        unpriced_runs=sum(_unpriced(u) for u in units),
        units=len(units),
        prompt_identified=len(identities),
        guide_versions=len({guide for guide in (_guide_version(i) for i in identities) if guide}),
    )


def _prompt_identity(unit: ProducerUnit) -> Mapping[str, object] | None:
    """The phase dispatch's ``metadata["prompt"]``, or None for a unit from before 177."""
    for action in unit.phase_step.action_results:
        if action.get("action_type") != ActionType.DISPATCH:
            continue
        metadata = action.get("metadata")
        if not isinstance(metadata, Mapping):
            continue
        identity = cast("Mapping[str, object]", metadata).get(PROMPT_METADATA_KEY)
        if isinstance(identity, Mapping):
            return cast("Mapping[str, object]", identity)
    return None


def _guide_version(identity: Mapping[str, object]) -> str | None:
    guide = identity.get("guide_version")
    return None if guide is None else str(guide)


def _section(phase: StepTypeName, units: list[_UnitUsage], min_n: int) -> PhaseSection:
    by_key: dict[ProducerKey, list[_UnitUsage]] = defaultdict(list)
    for usage in units:
        by_key[usage.unit.key].append(usage)
    rows = [_row(key, usages, min_n) for key, usages in by_key.items()]
    rows.sort(key=lambda row: (row.below_floor, -row.n, row.model or ""))
    runs = len({u.unit.run_id for u in units})
    return PhaseSection(phase=phase.value, runs=runs, rows=tuple(rows))


def _row(key: ProducerKey, usages: list[_UnitUsage], min_n: int) -> ProducerRow:
    members = [usage.unit for usage in usages]
    records = [record for usage in usages for record in usage.records]
    actions = sum(usage.llm_actions for usage in usages)
    totals = usage_totals(records)
    accepted = sum(phase_accepted(unit.phase_step, unit.loop_step) for unit in members)
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
        median_revise_rounds=float(statistics.median(loop_rounds(unit.loop_step) for unit in members)),
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


def _unpriced(usage: _UnitUsage) -> bool:
    """No priced record at all: a run from before 175, or one on an unpriced model."""
    return all(record.cost_usd is None for record in usage.records)


def _rounds_unrecorded(unit: ProducerUnit) -> bool:
    loop = unit.loop_step
    return loop is not None and not loop.prior_round_results and loop.iteration > 1


@dataclass(frozen=True)
class _UnitUsage:
    """A unit with its usage, read once so a malformed record warns once."""

    unit: ProducerUnit
    records: list[UsageRecord]
    llm_actions: int


def _usage(unit: ProducerUnit) -> _UnitUsage:
    """Usage records and LLM action count over the phase step and every loop round."""
    usage = unit_usage(unit.run_id, unit.phase_step, unit.loop_step)
    return _UnitUsage(unit, usage.records, usage.llm_actions)
