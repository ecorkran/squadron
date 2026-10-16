"""Build the ``sq replay report`` data: replays and judgments to one table per
(phase, reviewer, judge) (slice 177 D7).

Pairs are pooled across slices and contestants are configs (D1: alias, model, profile,
effort sent), not individual replays. A pair between two replays of the same config says
nothing about the config and is left out. Nothing here formats text.
"""

from __future__ import annotations

import logging
import statistics
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import NamedTuple, Protocol

from squadron.metrology.replay_models import (
    ORIGINAL_CONTESTANT_PREFIX,
    JudgeRef,
    ModelRef,
    PairOutcome,
    PairwiseJudgment,
    ProducerConfigRef,
    ProducerReplay,
    ReplayOutcome,
    ReplayPhase,
)
from squadron.replay.bradley_terry import BTFit, Comparison, fit
from squadron.replay.report_models import ORIGINAL_LABEL, ConfigRow, ReplayReport, ReplayTable

_logger = logging.getLogger(__name__)

_Replays = Sequence[tuple[str, ProducerReplay]]


class ReportStore(Protocol):
    def list_replays(
        self, project_id: str, phase: ReplayPhase | None = None, replay_set: str | None = None
    ) -> list[tuple[str, ProducerReplay]]: ...

    def list_judgments(
        self, project_id: str, phase: ReplayPhase | None = None, judge: JudgeRef | None = None
    ) -> list[PairwiseJudgment]: ...


def config_label(config: ProducerConfigRef) -> str:
    """The row key of D1, as text."""
    return (
        f"{config.alias} ({config.model}, {config.profile or 'no profile'}, "
        f"effort {config.effort_sent or 'none'})"
    )


class _Judged(NamedTuple):
    """The pairwise columns of a row."""

    strength: float | None
    strength_reason: str | None
    wins: int
    losses: int
    ties: int
    pairs: int
    invalid: int
    inconsistent: int
    below_floor: bool


@dataclass
class _Tally:
    wins: int = 0
    losses: int = 0
    ties: int = 0
    pairs: int = 0
    invalid: int = 0
    inconsistent: int = 0


def replay_report(
    *,
    project_id: str,
    phase: ReplayPhase | None,
    judge_alias: str | None,
    store: ReportStore,
    min_n: int,
) -> ReplayReport:
    """The report over every stored replay of ``project_id``, optionally for one judge alias."""
    replays = store.list_replays(project_id, phase)
    judgments = store.list_judgments(project_id, phase)
    if judge_alias is not None:
        judgments = [j for j in judgments if j.judge.alias == judge_alias]
    by_group: dict[tuple[ReplayPhase, str, str], list[tuple[str, ProducerReplay]]] = defaultdict(list)
    reviewers: dict[tuple[ReplayPhase, str, str], ModelRef] = {}
    reviewer_of_set: dict[str, ModelRef] = {}
    for record_id, replay in replays:
        key = (replay.phase, replay.reviewer.alias, replay.reviewer.model)
        by_group[key].append((record_id, replay))
        reviewers[key] = replay.reviewer
        reviewer_of_set[replay.replay_set] = replay.reviewer
    labels = {record_id: config_label(replay.config) for record_id, replay in replays}
    tables: list[ReplayTable] = []
    for key, members in sorted(by_group.items(), key=lambda group: group[0]):
        group_phase, reviewer = key[0], reviewers[key]
        mine = [
            j
            for j in judgments
            if reviewer_of_set.get(j.replay_set) == reviewer and j.phase == group_phase
        ]
        judges = {j.judge.model_dump_json(): j.judge for j in mine}
        for judge in sorted(judges.values(), key=lambda ref: (ref.alias, ref.prompt_hash)) or [None]:
            subset = [j for j in mine if judge is None or j.judge == judge]
            tables.append(_table(group_phase, reviewer, judge, members, subset, labels, min_n))
    return ReplayReport(min_n=min_n, tables=tuple(tables))


def _table(
    phase: ReplayPhase,
    reviewer: ModelRef,
    judge: JudgeRef | None,
    members: _Replays,
    judgments: Sequence[PairwiseJudgment],
    labels: dict[str, str],
    min_n: int,
) -> ReplayTable:
    comparisons, tallies = _pairs(judgments, labels)
    result = fit(comparisons)
    rows = _rows(members, tallies, result, min_n)
    verdicts = [j for j in judgments if j.outcome is not PairOutcome.INVALID]
    return ReplayTable(
        phase=phase,
        reviewer=reviewer,
        judge=judge,
        rows=rows,
        slices=tuple(sorted({replay.slice_index for _, replay in members})),
        consistent_pairs=sum(j.outcome is not PairOutcome.INCONSISTENT for j in verdicts),
        verdict_pairs=len(verdicts),
        prompt_identities=_identities(members),
        strengths_converged=result.converged,
        strength_components=len(result.components),
        self_preference=judge is not None and any(r.config.model == judge.model for _, r in members),
    )


def _label_of(ref: str, labels: dict[str, str]) -> str | None:
    if ref.startswith(ORIGINAL_CONTESTANT_PREFIX):
        return ORIGINAL_LABEL
    label = labels.get(ref)
    if label is None:
        _logger.warning("a judgment names replay %s, which is not in the store; it is skipped", ref)
    return label


def _pairs(
    judgments: Sequence[PairwiseJudgment], labels: dict[str, str]
) -> tuple[list[Comparison], dict[str, _Tally]]:
    comparisons: list[Comparison] = []
    tallies: dict[str, _Tally] = defaultdict(_Tally)
    for judgment in judgments:
        a, b = _label_of(judgment.a, labels), _label_of(judgment.b, labels)
        if a is None or b is None or a == b:
            continue  # unknown replay, or a config compared with itself
        comparisons.append(Comparison(a, b, judgment.outcome))
        for name in (a, b):
            tallies[name].pairs += 1
        _tally(judgment.outcome, tallies[a], tallies[b])
    return comparisons, tallies


def _tally(outcome: PairOutcome, first: _Tally, second: _Tally) -> None:
    match outcome:
        case PairOutcome.A:
            first.wins += 1
            second.losses += 1
        case PairOutcome.B:
            second.wins += 1
            first.losses += 1
        case PairOutcome.TIE | PairOutcome.INCONSISTENT:
            first.ties += 1
            second.ties += 1
            if outcome is PairOutcome.INCONSISTENT:
                first.inconsistent += 1
                second.inconsistent += 1
        case PairOutcome.INVALID:
            first.invalid += 1
            second.invalid += 1


def _rows(
    members: _Replays, tallies: dict[str, _Tally], result: BTFit, min_n: int
) -> tuple[ConfigRow, ...]:
    by_label: dict[str, list[ProducerReplay]] = defaultdict(list)
    for _, replay in members:
        by_label[config_label(replay.config)].append(replay)
    rows = [
        _config_row(label, group, tallies[label], result, min_n) for label, group in by_label.items()
    ]
    if ORIGINAL_LABEL in tallies:
        rows.append(_original_row(tallies[ORIGINAL_LABEL], result))
    ranked = sorted(
        (r for r in rows if r.config is not None and not r.below_floor and r.strength is not None),
        key=lambda r: -(r.strength or 0.0),
    )
    rank = {row.label: position for position, row in enumerate(ranked, start=1)}
    rows = [_with_rank(row, rank.get(row.label)) for row in rows]
    return tuple(sorted(rows, key=lambda r: (r.config is None, r.rank is None, r.rank or 0, r.label)))


def _config_row(
    label: str, group: list[ProducerReplay], tally: _Tally, result: BTFit, min_n: int
) -> ConfigRow:
    failed = sum(r.outcome is ReplayOutcome.FAILED for r in group)
    accepted = [r for r in group if r.outcome is ReplayOutcome.ACCEPTED]
    costs = [r.cost_usd for r in group if r.cost_usd is not None]
    rounds = [r.rounds for r in accepted if r.rounds is not None]
    judged = _judged(label, tally, result, min_n)
    return ConfigRow(
        label=label,
        config=group[0].config,
        n=len(group),
        failed=failed,
        accepted=len(accepted),
        accepted_of=len(group) - failed,
        median_rounds=_median(rounds),
        median_cost_usd=_median(costs),
        priced=sum(r.priced[0] for r in group),
        llm_actions=sum(r.priced[1] for r in group),
        median_wall_seconds=_median([r.wall_seconds for r in group]),
        strength=judged.strength,
        strength_reason=judged.strength_reason,
        wins=judged.wins,
        losses=judged.losses,
        ties=judged.ties,
        pairs=judged.pairs,
        invalid=judged.invalid,
        inconsistent=judged.inconsistent,
        below_floor=judged.below_floor,
        rank=None,
    )


def _original_row(tally: _Tally, result: BTFit) -> ConfigRow:
    judged = _judged(ORIGINAL_LABEL, tally, result, 0)
    return ConfigRow(
        label=ORIGINAL_LABEL,
        config=None,
        n=0,
        failed=0,
        accepted=0,
        accepted_of=0,
        median_rounds=None,
        median_cost_usd=None,
        priced=0,
        llm_actions=0,
        median_wall_seconds=None,
        strength=judged.strength,
        strength_reason=judged.strength_reason,
        wins=judged.wins,
        losses=judged.losses,
        ties=judged.ties,
        pairs=judged.pairs,
        invalid=judged.invalid,
        inconsistent=judged.inconsistent,
        below_floor=judged.below_floor,
        rank=None,
    )


def _judged(label: str, tally: _Tally, result: BTFit, min_n: int) -> _Judged:
    strength = result.strengths.get(label)
    return _Judged(
        strength=None if strength is None else strength.value,
        strength_reason=None if strength is None else strength.reason,
        wins=tally.wins,
        losses=tally.losses,
        ties=tally.ties,
        pairs=tally.pairs,
        invalid=tally.invalid,
        inconsistent=tally.inconsistent,
        below_floor=tally.pairs - tally.invalid < min_n,
    )


def _with_rank(row: ConfigRow, rank: int | None) -> ConfigRow:
    return replace(row, rank=rank)


def _median(values: Sequence[float | int]) -> float | None:
    return float(statistics.median(values)) if values else None


def _identities(members: _Replays) -> tuple[str, ...]:
    seen = {
        f"squadron {r.prompt.squadron_version}, cf {r.prompt.cf_version or 'unknown'}, "
        f"guide {r.prompt.guide_version or 'unknown'}"
        for _, r in members
        if r.prompt is not None
    }
    return tuple(sorted(seen))
