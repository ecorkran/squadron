"""Bradley-Terry strengths from pairwise outcomes (slice 177 D6).

Hunter's MM iteration over win counts, with a tie counted as half a win to each side. Elo
depends on the order games are played; this fits all comparisons at once and handles an
incomplete comparison graph, which pooling pairs across slices gives. A pure function with
no dependency.

Two kinds of contestant have no finite maximum-likelihood strength and are reported as
``None`` with the reason, not forced to a number by a prior: one with no wins, and one
that never lost. Removing them can strand others, so they are removed until none is left.
Strengths are normalized to a geometric mean of 1 within each connected component.
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from squadron.metrology.replay_models import PairOutcome

_logger = logging.getLogger(__name__)

TOLERANCE = 1e-9
MAX_ITERATIONS = 10_000

NO_WINS = "no wins, so its strength is zero"
NEVER_LOST = "never lost, so its strength is unbounded"


@dataclass(frozen=True)
class Comparison:
    """One judged pair: contestant ``a`` against ``b``; ``A`` means ``a`` won."""

    a: str
    b: str
    outcome: PairOutcome


@dataclass(frozen=True)
class Strength:
    value: float | None  # None when no finite strength exists
    reason: str | None  # why, when value is None
    component: int | None  # index into BTFit.components


@dataclass(frozen=True)
class BTFit:
    strengths: dict[str, Strength]
    components: tuple[tuple[str, ...], ...]  # contestants of each connected group, fitted apart
    iterations: int
    converged: bool


@dataclass
class _Game:
    """Win credit for ``a`` (1, 0.5 or 0) in one comparison between ``a`` and ``b``."""

    a: str
    b: str
    credit: float


def fit(comparisons: Sequence[Comparison]) -> BTFit:
    """Fit strengths to ``comparisons``. ``INVALID`` is excluded; ``INCONSISTENT`` is a tie."""
    games = [g for c in comparisons if (g := _game(c)) is not None]
    strengths: dict[str, Strength] = {}
    games = _prune(games, strengths)
    components = _components(games)
    iterations, converged = 0, True
    for index, members in enumerate(components):
        values, used, done = _fit_component([g for g in games if g.a in members], sorted(members))
        iterations, converged = max(iterations, used), converged and done
        for name, value in values.items():
            strengths[name] = Strength(value=value, reason=None, component=index)
    if not converged:
        _logger.warning(
            "Bradley-Terry fit stopped at the %d-iteration cap before converging", MAX_ITERATIONS
        )
    return BTFit(
        strengths=strengths,
        components=tuple(tuple(sorted(c)) for c in components),
        iterations=iterations,
        converged=converged,
    )


def _game(comparison: Comparison) -> _Game | None:
    match comparison.outcome:
        case PairOutcome.A:
            return _Game(comparison.a, comparison.b, 1.0)
        case PairOutcome.B:
            return _Game(comparison.a, comparison.b, 0.0)
        case PairOutcome.TIE | PairOutcome.INCONSISTENT:
            return _Game(comparison.a, comparison.b, 0.5)
        case PairOutcome.INVALID:
            return None


def _prune(games: list[_Game], strengths: dict[str, Strength]) -> list[_Game]:
    """Drop contestants with no finite strength, and their games, until none is left."""
    while True:
        wins: dict[str, float] = defaultdict(float)
        played: dict[str, int] = defaultdict(int)
        for g in games:
            wins[g.a] += g.credit
            wins[g.b] += 1 - g.credit
            played[g.a] += 1
            played[g.b] += 1
        dropped = {
            name: (NO_WINS if wins[name] == 0 else NEVER_LOST)
            for name in played
            if wins[name] == 0 or wins[name] == played[name]
        }
        if not dropped:
            return games
        for name, reason in dropped.items():
            strengths[name] = Strength(value=None, reason=reason, component=None)
        games = [g for g in games if g.a not in dropped and g.b not in dropped]


def _components(games: list[_Game]) -> list[set[str]]:
    groups: list[set[str]] = []
    for g in games:
        touching = [group for group in groups if g.a in group or g.b in group]
        merged = {g.a, g.b}.union(*touching)
        groups = [group for group in groups if group not in touching] + [merged]
    return sorted(groups, key=lambda group: sorted(group))


def _fit_component(games: list[_Game], members: list[str]) -> tuple[dict[str, float], int, bool]:
    wins: dict[str, float] = defaultdict(float)
    for g in games:
        wins[g.a] += g.credit
        wins[g.b] += 1 - g.credit
    strength = dict.fromkeys(members, 1.0)
    for iteration in range(1, MAX_ITERATIONS + 1):
        denominator: dict[str, float] = defaultdict(float)
        for g in games:
            share = 1 / (strength[g.a] + strength[g.b])
            denominator[g.a] += share
            denominator[g.b] += share
        updated = {name: wins[name] / denominator[name] for name in members}
        mean = math.exp(sum(math.log(v) for v in updated.values()) / len(updated))
        updated = {name: value / mean for name, value in updated.items()}
        change = max(abs(updated[name] - strength[name]) for name in members)
        strength = updated
        if change < TOLERANCE:
            return strength, iteration, True
    return strength, MAX_ITERATIONS, False
