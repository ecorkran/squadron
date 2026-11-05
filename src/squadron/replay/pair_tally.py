"""Turn judgments into Bradley-Terry comparisons and per-contestant tallies (slice 177 D7).

Contestants are the row labels of a report table. A judgment naming a replay the store
does not hold, or a config compared with itself, is left out.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from squadron.metrology.replay_models import (
    ORIGINAL_CONTESTANT_PREFIX,
    PairOutcome,
    PairwiseJudgment,
)
from squadron.replay.bradley_terry import Comparison
from squadron.replay.report_models import ORIGINAL_LABEL

_logger = logging.getLogger(__name__)


@dataclass
class Tally:
    wins: int = 0
    losses: int = 0
    ties: int = 0
    pairs: int = 0
    invalid: int = 0
    inconsistent: int = 0


def tally_pairs(
    judgments: Sequence[PairwiseJudgment], labels: dict[str, str]
) -> tuple[list[Comparison], dict[str, Tally]]:
    """The comparisons the fit needs and each contestant's win/loss/tie counts."""
    comparisons: list[Comparison] = []
    tallies: dict[str, Tally] = defaultdict(Tally)
    for judgment in judgments:
        a, b = _label_of(judgment.a, labels), _label_of(judgment.b, labels)
        if a is None or b is None or a == b:
            continue  # unknown replay, or a config compared with itself
        comparisons.append(Comparison(a, b, judgment.outcome))
        for name in (a, b):
            tallies[name].pairs += 1
        _tally(judgment.outcome, tallies[a], tallies[b])
    return comparisons, tallies


def _label_of(ref: str, labels: dict[str, str]) -> str | None:
    if ref.startswith(ORIGINAL_CONTESTANT_PREFIX):
        return ORIGINAL_LABEL
    label = labels.get(ref)
    if label is None:
        _logger.warning("a judgment names replay %s, which is not in the store; it is skipped", ref)
    return label


def _tally(outcome: PairOutcome, first: Tally, second: Tally) -> None:
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
