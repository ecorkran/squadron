"""Contestants, pairing and forfeits for judging slice-case diffs (slice 426 D13, D15).

Pure: no I/O. A contestant is one replay of a case or the reference; pairs are the
sample-matched cross-config comparisons plus each replay against the reference. A pair with
a config-absent side is a forfeit decided without a judge call; a case with a harness-absent
replay is not judged at all.
"""

from __future__ import annotations

import itertools
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import NamedTuple

from squadron.benchmark.grade_matrix import RowKey, row_key_of
from squadron.metrology.benchmark_models import BenchmarkCase
from squadron.metrology.benchmark_replay_enums import AbsenceClass, ProducerOutcome
from squadron.metrology.benchmark_replay_models import ImplementationReplay
from squadron.metrology.replay_models import JudgeRef, PairOutcome
from squadron.metrology.slice_case_models import DiffJudgment

REFERENCE_PREFIX = "reference:"
REFERENCE_LABEL = "reference"


class ContestantKind(StrEnum):
    REPLAY = "replay"
    REFERENCE = "reference"


class ReferenceAbsentError(Exception):
    """The reference diff is missing, so no pair of the case can be judged against it."""


class ReplayInput(NamedTuple):
    """One stored replay and its diff bytes (``None`` when it committed nothing)."""

    record_id: str
    replay: ImplementationReplay
    diff: bytes | None


@dataclass(frozen=True)
class Contestant:
    ref: str  # a replay record id, or ``reference:<tip sha>``
    kind: ContestantKind
    label: str  # the config's alias, or ``reference``
    config: RowKey | None  # ``None`` for the reference
    sample: int | None  # ``None`` for the reference
    diff: bytes | None  # ``None`` when absent
    #: Why a replay has no diff: its config absence (``no_commit``, ``blocked``, ``cost_cap``,
    #: ``producer_failed``). ``None`` when the contestant has a diff.
    absence: ProducerOutcome | None = None

    @property
    def present(self) -> bool:
        return self.absence is None


@dataclass(frozen=True)
class Pair:
    a: Contestant
    b: Contestant

    @property
    def versus_reference(self) -> bool:
        return self.b.kind is ContestantKind.REFERENCE


class Judgeability(NamedTuple):
    """Whether a case can be judged; ``reason`` names the harness absence when it cannot."""

    judgeable: bool
    reason: str | None


def case_judgeable(replays: Sequence[ReplayInput]) -> Judgeability:
    """False when any replay carries a harness absence (D15); the reason is its outcome value."""
    for item in replays:
        if item.replay.absence is AbsenceClass.HARNESS:
            return Judgeability(False, item.replay.outcome.value)
    return Judgeability(True, None)


def contestants_for(
    case: BenchmarkCase, replays: Sequence[ReplayInput], reference_diff: bytes
) -> list[Contestant]:
    """Each replay of the case, then the reference.

    A harness-absent replay is a caller bug (``case_judgeable`` comes first), and so is a
    committed replay with no diff; both raise ``ValueError``.
    """
    found = [_replay_contestant(item) for item in replays]
    found.append(
        Contestant(
            ref=f"{REFERENCE_PREFIX}{case.reference_sha}",
            kind=ContestantKind.REFERENCE,
            label=REFERENCE_LABEL,
            config=None,
            sample=None,
            diff=reference_diff,
        )
    )
    return found


def _replay_contestant(item: ReplayInput) -> Contestant:
    replay = item.replay
    if replay.absence is AbsenceClass.HARNESS:
        raise ValueError(f"replay {item.record_id} has a harness absence: {replay.outcome.value}")
    absence = replay.outcome if replay.absence is AbsenceClass.CONFIG else None
    if absence is None and item.diff is None:
        raise ValueError(f"replay {item.record_id} committed but has no diff")
    return Contestant(
        ref=item.record_id,
        kind=ContestantKind.REPLAY,
        label=replay.config.alias,
        config=row_key_of(replay),
        sample=replay.sample,
        diff=None if absence is not None else item.diff,
        absence=absence,
    )


def pairs_for(contestants: Sequence[Contestant]) -> list[Pair]:
    """Cross-config pairs matched by sample number, then each replay against the reference.

    For each pair of configs and each sample number both have, A's sample is judged against
    B's. Nothing is paired within one config. The order is fixed: configs by identity,
    samples ascending, the reference pairs last.
    """
    references = [c for c in contestants if c.kind is ContestantKind.REFERENCE]
    by_config: dict[str, dict[int, Contestant]] = {}
    for contestant in contestants:
        if contestant.kind is not ContestantKind.REPLAY:
            continue
        if contestant.config is None or contestant.sample is None:
            raise ValueError(f"replay contestant {contestant.ref} has no config or sample")
        by_config.setdefault(contestant.config.identity_text, {})[contestant.sample] = contestant
    pairs: list[Pair] = []
    for first, second in itertools.combinations(sorted(by_config), 2):
        shared = sorted(by_config[first].keys() & by_config[second].keys())
        pairs.extend(Pair(by_config[first][s], by_config[second][s]) for s in shared)
    for reference in references:
        for config_text in sorted(by_config):
            pairs.extend(
                Pair(by_config[config_text][s], reference) for s in sorted(by_config[config_text])
            )
    return pairs


def forfeit_for(pair: Pair) -> PairOutcome | None:
    """The outcome of a pair with an absent side, ``None`` when both sides have diffs.

    The present side wins; both sides absent is a ``TIE``. An absent reference raises.
    """
    if pair.b.kind is ContestantKind.REFERENCE and pair.b.diff is None:
        raise ReferenceAbsentError(f"reference {pair.b.ref} has no diff")
    a_present, b_present = pair.a.present, pair.b.present
    if a_present and b_present:
        return None
    if a_present:
        return PairOutcome.A
    if b_present:
        return PairOutcome.B
    return PairOutcome.TIE


def forfeit_judgment(
    *,
    benchmark_id: str,
    case_id: str,
    pair: Pair,
    outcome: PairOutcome,
    diff_hashes: Mapping[str, str],
    judge: JudgeRef,
    max_prompt_chars: int,
    created_at: datetime,
) -> DiffJudgment:
    """The record of a forfeit: no calls, no usage, and a sidecar hash only for a present side."""
    return DiffJudgment(
        benchmark_id=benchmark_id,
        case_id=case_id,
        judge=judge,
        a=pair.a.ref,
        b=pair.b.ref,
        a_diff=diff_hashes.get(pair.a.ref) if pair.a.present else None,
        b_diff=diff_hashes.get(pair.b.ref) if pair.b.present else None,
        forfeit=True,
        first_call=None,
        second_call=None,
        outcome=outcome,
        first_usage=None,
        second_usage=None,
        max_prompt_chars=max_prompt_chars,
        created_at=created_at,
    )
