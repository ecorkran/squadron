"""Build the ``sq replay report`` data: replays and judgments to one table per
(phase, reviewer, judge) (slice 177 D7).

Pairs are pooled across slices and contestants are configs, not individual replays. A
config is what went on the wire (slice 420 D6: model, profile, effort sent, tool use, output
budget), so two aliases that sent the same thing are one contestant. A pair between two
replays of the same config says nothing about the config and is left out. Nothing here
formats text.
"""

from __future__ import annotations

import logging
import statistics
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import replace
from typing import NamedTuple, Protocol

from squadron.metrology.replay_models import (
    JudgeRef,
    ModelRef,
    PairOutcome,
    PairwiseJudgment,
    ProducerConfigRef,
    ProducerReplay,
    ReplayOutcome,
    ReplayPhase,
)
from squadron.replay.bradley_terry import BTFit, Strength, fit
from squadron.replay.config_label import ConfigIdentity, config_label
from squadron.replay.pair_tally import Tally, tally_pairs
from squadron.replay.report_models import ORIGINAL_LABEL, ConfigRow, ReplayReport, ReplayTable

_logger = logging.getLogger(__name__)

NO_FIT_OPPONENTS = (
    "every opponent it met has no finite strength, so there is nothing to compare it with"
)

_Replays = Sequence[tuple[str, ProducerReplay]]


class ReportStore(Protocol):
    def list_replays(
        self, project_id: str, phase: ReplayPhase | None = None, replay_set: str | None = None
    ) -> list[tuple[str, ProducerReplay]]: ...

    def list_judgments(
        self, project_id: str, phase: ReplayPhase | None = None, judge: JudgeRef | None = None
    ) -> list[PairwiseJudgment]: ...


def _config_identity(config: ProducerConfigRef) -> ConfigIdentity:
    """What went on the wire, and so the grouping key for rows and contestants (D6).

    Records written before ``tool_use`` was recorded carry ``None`` and so group apart from
    new ones, by design; re-running the replay merges them.
    """
    return ConfigIdentity(
        model=config.model,
        profile=config.profile,
        effort_sent=config.effort_sent,
        tool_use=config.tool_use,
        max_output_tokens=config.max_output_tokens,
    )


def _labels(members: _Replays) -> dict[str, str]:
    """Each replay's row label; a row names every alias that sent the same config."""
    aliases: dict[ConfigIdentity, set[str]] = defaultdict(set)
    for _, replay in members:
        aliases[_config_identity(replay.config)].add(replay.config.alias)
    return {
        record_id: config_label(identity := _config_identity(replay.config), sorted(aliases[identity]))
        for record_id, replay in members
    }


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
            tables.append(_table(group_phase, reviewer, judge, members, subset, min_n))
    return ReplayReport(min_n=min_n, tables=tuple(tables))


def _table(
    phase: ReplayPhase,
    reviewer: ModelRef,
    judge: JudgeRef | None,
    members: _Replays,
    judgments: Sequence[PairwiseJudgment],
    min_n: int,
) -> ReplayTable:
    labels = _labels(members)
    comparisons, tallies = tally_pairs(judgments, labels)
    result = fit(comparisons)
    rows = _rows(members, labels, tallies, result, min_n)
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


def _rows(
    members: _Replays, labels: dict[str, str], tallies: dict[str, Tally], result: BTFit, min_n: int
) -> tuple[ConfigRow, ...]:
    by_label: dict[str, list[ProducerReplay]] = defaultdict(list)
    for record_id, replay in members:
        by_label[labels[record_id]].append(replay)
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
    label: str, group: list[ProducerReplay], tally: Tally, result: BTFit, min_n: int
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


def _original_row(tally: Tally, result: BTFit) -> ConfigRow:
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


def _judged(label: str, tally: Tally, result: BTFit, min_n: int) -> _Judged:
    strength = result.strengths.get(label)
    return _Judged(
        strength=None if strength is None else strength.value,
        strength_reason=_strength_reason(strength, tally),
        wins=tally.wins,
        losses=tally.losses,
        ties=tally.ties,
        pairs=tally.pairs,
        invalid=tally.invalid,
        inconsistent=tally.inconsistent,
        below_floor=tally.pairs - tally.invalid < min_n,
    )


def _strength_reason(strength: Strength | None, tally: Tally) -> str | None:
    """Why a row has no strength: the fit's own reason, or that every opponent had none."""
    if strength is not None:
        return strength.reason
    if tally.pairs - tally.invalid > 0:
        return NO_FIT_OPPONENTS
    return None


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
