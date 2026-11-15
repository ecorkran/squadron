"""Reducing diff judgments to the pairwise section of the report (slice 426 D15, D17).

Pure: records in, a ``PairwiseSection`` out. Strengths come from the pairwise fit over every
judged pair of the included slice cases, with config row keys and ``reference`` as
contestants; the reference is fitted but never ranked. Each pair of configs gets a verdict from
a paired bootstrap over cases of ``d(c) = 2·w(c) − 1``, where ``w(c)`` is A's win share over
the sample-matched pairs of case ``c`` (a win counts 1, a tie 0.5; inconsistent and invalid
pairs are left out). No composite is computed: the section never touches the objective grade.
"""

from __future__ import annotations

import itertools
import logging
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from squadron.benchmark.diff_pairs import (
    REFERENCE_PREFIX,
    ReplayInput,
    contestants_for,
    pairs_for,
)
from squadron.benchmark.grade_matrix import Exclusion, GradeMatrix, RowKey, row_key_of
from squadron.benchmark.pair_row import PairRow
from squadron.benchmark.paired_stats import compare_pair, pair_seed
from squadron.benchmark.pairwise_models import (
    OtherJudge,
    PairwiseConfigRow,
    PairwiseCounts,
    PairwiseReference,
    PairwiseSection,
)
from squadron.metrology.benchmark_models import BenchmarkCase, CaseKind
from squadron.metrology.benchmark_replay_models import ImplementationReplay
from squadron.metrology.replay_models import PairOutcome
from squadron.metrology.slice_case_models import DiffJudgment, OverSizeCase
from squadron.replay.bradley_terry import Comparison, Strength, fit

_logger = logging.getLogger(__name__)

REFERENCE = "reference"
_HARNESS_EXCLUSIONS = (Exclusion.HARNESS_REPLAY, Exclusion.HARNESS_GRADE)


@dataclass
class _Tally:
    wins: int = 0
    losses: int = 0
    ties: int = 0
    inconsistent: int = 0
    invalid: int = 0
    forfeits: int = 0
    pairs: int = 0


def build_pairwise(
    *,
    benchmark_id: str,
    matrix: GradeMatrix,
    cases: Mapping[str, BenchmarkCase],
    replays: Sequence[tuple[str, ImplementationReplay]],
    judgments: Sequence[DiffJudgment],
    over_size: Sequence[OverSizeCase],
) -> PairwiseSection | None:
    """The section for the latest judge, ``None`` when nothing was judged or counted."""
    judge = _latest_judge(judgments, over_size)
    if judge is None:
        return None
    mine = [j for j in judgments if _judge_of(j) == judge]
    others = _others(judgments, judge)
    slice_cases = [c for c in matrix.included_cases if cases[c].kind is CaseKind.SLICE]
    if not slice_cases:
        return None
    slice_case_ids = set(slice_cases)
    included = [j for j in mine if j.case_id in slice_case_ids]
    rows = {rid: row_key_of(replay) for rid, replay in replays}
    labels = {key.identity_text: matrix.labels.get(key, key.model) for key in set(rows.values())}
    configs, reference = _strengths(included, rows, labels)
    return PairwiseSection(
        judge_alias=judge[0],
        prompt_hash=judge[1],
        configs=configs,
        reference=reference,
        pairs=_pairs(benchmark_id, matrix, included, rows, slice_cases),
        counts=_counts(matrix, cases, replays, included, over_size, judge, slice_cases),
        others=others,
    )


def _judge_of(item: DiffJudgment | OverSizeCase) -> tuple[str, str]:
    return item.judge.alias, item.judge.prompt_hash


def _latest_judge(
    judgments: Sequence[DiffJudgment], over_size: Sequence[OverSizeCase]
) -> tuple[str, str] | None:
    records = [*judgments, *over_size]
    if not records:
        return None
    return _judge_of(max(records, key=lambda record: record.created_at))


def _others(judgments: Sequence[DiffJudgment], judge: tuple[str, str]) -> tuple[OtherJudge, ...]:
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for item in judgments:
        if _judge_of(item) != judge:
            counts[_judge_of(item)] += 1
    return tuple(
        OtherJudge(alias=a, prompt_hash=h, judgments=n) for (a, h), n in sorted(counts.items())
    )


def _contestant(ref: str, rows: Mapping[str, RowKey]) -> str | None:
    """A contestant's name in the fit: its config identity, or ``reference``."""
    if ref.startswith(REFERENCE_PREFIX):
        return REFERENCE
    key = rows.get(ref)
    if key is None:
        _logger.warning("a judgment names replay %s, which is not in the benchmark; it is skipped", ref)
        return None
    return key.identity_text


def _strengths(
    judgments: Sequence[DiffJudgment], rows: Mapping[str, RowKey], labels: Mapping[str, str]
) -> tuple[tuple[PairwiseConfigRow, ...], PairwiseReference | None]:
    comparisons: list[Comparison] = []
    tallies: dict[str, _Tally] = defaultdict(_Tally)
    for judgment in judgments:
        a, b = _contestant(judgment.a, rows), _contestant(judgment.b, rows)
        if a is None or b is None or a == b or judgment.outcome is None:
            continue
        comparisons.append(Comparison(a, b, judgment.outcome))
        _tally(judgment.outcome, judgment.forfeit, tallies[a], tallies[b])
    strengths = fit(comparisons).strengths
    configs = tuple(
        _config_row(
            identity, labels.get(identity, identity), tallies[identity], strengths.get(identity)
        )
        for identity in sorted(tallies)
        if identity != REFERENCE
    )
    reference = strengths.get(REFERENCE)
    return configs, None if reference is None else PairwiseReference(
        strength=reference.value, reason=reference.reason
    )


def _config_row(
    identity: str, label: str, tally: _Tally, strength: Strength | None
) -> PairwiseConfigRow:
    return PairwiseConfigRow(
        label=label,
        identity=identity,
        strength=None if strength is None else strength.value,
        reason=None if strength is None else strength.reason,
        wins=tally.wins,
        losses=tally.losses,
        ties=tally.ties,
        inconsistent=tally.inconsistent,
        invalid=tally.invalid,
        forfeits=tally.forfeits,
        pairs=tally.pairs,
    )


def _tally(outcome: PairOutcome, forfeit: bool, first: _Tally, second: _Tally) -> None:
    for side in (first, second):
        side.pairs += 1
        side.forfeits += forfeit
    match outcome:
        case PairOutcome.A:
            first.wins += 1
            second.losses += 1
        case PairOutcome.B:
            second.wins += 1
            first.losses += 1
        case PairOutcome.TIE:
            first.ties += 1
            second.ties += 1
        case PairOutcome.INCONSISTENT:
            first.inconsistent += 1
            second.inconsistent += 1
        case PairOutcome.INVALID:
            first.invalid += 1
            second.invalid += 1


def _win_share(
    judgments: Sequence[DiffJudgment], key_a: str, key_b: str, rows: Mapping[str, RowKey]
) -> float | None:
    """A's share of the case's judged pairs between configs a and b; ``None`` when none count."""
    credit, counted = 0.0, 0
    for judgment in judgments:
        first, second = _contestant(judgment.a, rows), _contestant(judgment.b, rows)
        if {first, second} != {key_a, key_b} or judgment.outcome is None:
            continue
        outcome = judgment.outcome
        if first == key_b:  # the judgment names b first: flip it to a's point of view
            outcome = {PairOutcome.A: PairOutcome.B, PairOutcome.B: PairOutcome.A}.get(outcome, outcome)
        if outcome in (PairOutcome.INCONSISTENT, PairOutcome.INVALID):
            continue
        counted += 1
        credit += {PairOutcome.A: 1.0, PairOutcome.TIE: 0.5}.get(outcome, 0.0)
    return None if counted == 0 else credit / counted


def _pairs(
    benchmark_id: str,
    matrix: GradeMatrix,
    judgments: Sequence[DiffJudgment],
    rows: Mapping[str, RowKey],
    cases: Sequence[str],
) -> tuple[PairRow, ...]:
    by_case: dict[str, list[DiffJudgment]] = defaultdict(list)
    for judgment in judgments:
        by_case[judgment.case_id].append(judgment)
    out: list[PairRow] = []
    for a, b in itertools.combinations(
        sorted(matrix.comparable_rows, key=lambda r: r.identity_text), 2
    ):
        differences = [
            2 * share - 1
            for case in cases
            if (share := _win_share(by_case.get(case, ()), a.identity_text, b.identity_text, rows))
            is not None
        ]
        result = compare_pair(differences, pair_seed(benchmark_id, a.identity_text, b.identity_text))
        out.append(
            PairRow(
                label_a=matrix.labels[a],
                label_b=matrix.labels[b],
                n_cases=result.n,
                mean_difference=result.mean,
                low=result.low,
                high=result.high,
                verdict=result.verdict,
            )
        )
    return tuple(out)


def _counts(
    matrix: GradeMatrix,
    cases: Mapping[str, BenchmarkCase],
    replays: Sequence[tuple[str, ImplementationReplay]],
    judgments: Sequence[DiffJudgment],
    over_size: Sequence[OverSizeCase],
    judge: tuple[str, str],
    slice_cases: Sequence[str],
) -> PairwiseCounts:
    judged_cases = {j.case_id for j in judgments}
    # A stale over-size record stays after the limit is raised; the case counts as over size
    # only while the judge has no judgment for it.
    over = [
        o
        for o in over_size
        if _judge_of(o) == judge and o.case_id in set(slice_cases) and o.case_id not in judged_cases
    ]
    absent = [
        c
        for c, reason in matrix.excluded.items()
        if reason in _HARNESS_EXCLUSIONS and cases[c].kind is CaseKind.SLICE
    ]
    newest = max(over, key=lambda o: o.created_at, default=None)
    return PairwiseCounts(
        judged=len(judged_cases),
        over_size=len(over),
        over_size_limit=None if newest is None else newest.max_prompt_chars,
        harness_absent=len(absent),
        pending=_pending(cases, replays, judgments, judged_cases),
    )


def _pending(
    cases: Mapping[str, BenchmarkCase],
    replays: Sequence[tuple[str, ImplementationReplay]],
    judgments: Sequence[DiffJudgment],
    judged_cases: set[str],
) -> int:
    """Pairs of judged cases that have no record: failed or stopped before their calls."""
    recorded: dict[str, set[frozenset[str]]] = defaultdict(set)
    for judgment in judgments:
        recorded[judgment.case_id].add(frozenset((judgment.a, judgment.b)))
    pending = 0
    for case_id in sorted(judged_cases):
        inputs = [
            ReplayInput(rid, replay, b"")  # pairing reads no diff bytes
            for rid, replay in replays
            if replay.case_id == case_id
        ]
        pairs = pairs_for(contestants_for(cases[case_id], inputs, b""))
        expected = {frozenset((p.a.ref, p.b.ref)) for p in pairs}
        pending += len(expected - recorded[case_id])
    return pending
