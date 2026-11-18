"""Paired intervals for every pair of report rows (slice 430 D12). Pure.

Per pair: the cases both rows have complete (every requested run scored) and with nothing
undecided in either. Each row reduces to one value per case, recall and separately
findings per run; ``paired_stats.compare_pair`` gives the mean difference and its
bootstrap interval, seeded by ``pair_seed("<set>@v<n>", key_a, key_b)``.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from enum import StrEnum

from squadron.benchmark.paired_stats import PairComparison, compare_pair, pair_seed
from squadron.benchmark.recall.scoring import RowOutputs
from squadron.benchmark.recall.scoring_metrics import LabelsByCase, per_case_scores
from squadron.benchmark.recall.scoring_pair import PairScore
from squadron.metrology.grade_models import PairVerdict

#: The runbook's floor of usable shared cases for a paired interval.
MIN_RECALL_PAIRED_CASES = 8


class PairedMetric(StrEnum):
    RECALL = "recall"
    FINDINGS_PER_RUN = "findings/run"


@dataclass(frozen=True)
class CaseValue:
    recall: float
    findings_per_run: float
    undecided: bool


@dataclass(frozen=True)
class PairedLine:
    label_a: str
    label_b: str
    metric: PairedMetric
    comparison: PairComparison
    left_out_undecided: int


def case_values(row: RowOutputs, labels: LabelsByCase, run_indexes: list[int]) -> dict[str, CaseValue]:
    """Per complete case of *row*: recall and findings/run (a pool's member mean)."""
    values: dict[str, CaseValue] = {}
    for case_id, members in per_case_scores(row, labels).items():
        if any(len(scores) != len(run_indexes) for scores in members):
            continue
        per_member = [_member_value(scores) for scores in members]
        values[case_id] = CaseValue(
            recall=math.fsum(v.recall for v in per_member) / len(per_member),
            findings_per_run=math.fsum(v.findings_per_run for v in per_member) / len(per_member),
            undecided=any(v.undecided for v in per_member),
        )
    return values


def _member_value(scores: list[PairScore]) -> CaseValue:
    slots = sum(s.bug_count for s in scores)
    hits = sum(len(s.hit_low) for s in scores)
    return CaseValue(
        recall=hits / slots if slots else 0.0,
        findings_per_run=sum(s.findings for s in scores) / len(scores),
        undecided=any(s.undecided for s in scores),
    )


def paired_lines(
    rows: list[RowOutputs], labels: LabelsByCase, run_indexes: list[int], benchmark_id: str
) -> list[PairedLine]:
    """Both metrics for every row pair, in report order."""
    values = {row.key: case_values(row, labels, run_indexes) for row in rows}
    lines: list[PairedLine] = []
    for row_a, row_b in itertools.combinations(rows, 2):
        a, b = values[row_a.key], values[row_b.key]
        shared = sorted(set(a) & set(b))
        usable = [c for c in shared if not (a[c].undecided or b[c].undecided)]
        seed = pair_seed(benchmark_id, row_a.key, row_b.key)
        for metric in PairedMetric:
            differences = [_value(a[c], metric) - _value(b[c], metric) for c in usable]
            lines.append(
                PairedLine(
                    label_a=row_a.label,
                    label_b=row_b.label,
                    metric=metric,
                    comparison=_compare(differences, seed),
                    left_out_undecided=len(shared) - len(usable),
                )
            )
    return lines


def _value(value: CaseValue, metric: PairedMetric) -> float:
    return value.recall if metric is PairedMetric.RECALL else value.findings_per_run


def _compare(differences: list[float], seed: int) -> PairComparison:
    if len(differences) < MIN_RECALL_PAIRED_CASES:
        mean = math.fsum(differences) / len(differences) if differences else 0.0
        return PairComparison(len(differences), mean, None, None, PairVerdict.TOO_FEW_CASES)
    return compare_pair(differences, seed)
