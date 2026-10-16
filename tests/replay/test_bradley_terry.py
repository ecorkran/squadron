"""The Bradley-Terry fit against hand-computed cases (slice 177 D6)."""

from __future__ import annotations

import logging
import math

import pytest

from squadron.metrology.replay_models import PairOutcome
from squadron.replay import bradley_terry
from squadron.replay.bradley_terry import NEVER_LOST, NO_WINS, Comparison, fit

A, B, TIE = PairOutcome.A, PairOutcome.B, PairOutcome.TIE


def _games(first: str, second: str, wins_first: int, wins_second: int) -> list[Comparison]:
    return [Comparison(first, second, A)] * wins_first + [Comparison(first, second, B)] * wins_second


def _value(result: bradley_terry.BTFit, name: str) -> float:
    value = result.strengths[name].value
    assert value is not None
    return value


def test_a_three_contestant_chain_matches_the_hand_computed_strengths() -> None:
    # A beats B 3-1 and B beats C 3-1; A and C never meet.
    #   W_A = 3, W_B = 1 + 3 = 4, W_C = 1; n_AB = 4, n_BC = 4.
    # The MM fixed point satisfies p_A = (3/4)(p_A + p_B) -> p_A = 3 p_B,
    #                              p_C = (1/4)(p_B + p_C) -> p_C = p_B / 3,
    # and p_B = 4 / (4/(p_A+p_B) + 4/(p_B+p_C)) = 1 holds for (3, 1, 1/3), whose geometric
    # mean is (3 * 1 * 1/3)^(1/3) = 1, so these are already the normalized strengths.
    result = fit([*_games("A", "B", 3, 1), *_games("B", "C", 3, 1)])

    assert _value(result, "A") == pytest.approx(3.0, rel=1e-6)
    assert _value(result, "B") == pytest.approx(1.0, rel=1e-6)
    assert _value(result, "C") == pytest.approx(1 / 3, rel=1e-6)
    assert result.converged and result.components == (("A", "B", "C"),)


def test_strengths_have_a_geometric_mean_of_one() -> None:
    result = fit([*_games("A", "B", 5, 2), *_games("B", "C", 4, 3), *_games("A", "C", 6, 1)])

    values = [_value(result, name) for name in "ABC"]
    assert math.prod(values) == pytest.approx(1.0, rel=1e-6)
    assert values[0] > values[1] > values[2]


def test_a_two_contestant_ratio_is_the_win_ratio() -> None:
    result = fit(_games("A", "B", 3, 1))

    # p_A / p_B = 3 and p_A * p_B = 1, so p_A = sqrt(3) and p_B = 1 / sqrt(3).
    assert _value(result, "A") == pytest.approx(math.sqrt(3), rel=1e-6)
    assert _value(result, "B") == pytest.approx(1 / math.sqrt(3), rel=1e-6)


def test_a_contestant_with_no_wins_has_no_strength_and_a_reason() -> None:
    # C loses to both. Without C, A beats B 3-1.
    games = [*_games("A", "B", 3, 1), *_games("A", "C", 2, 0), *_games("B", "C", 2, 0)]

    result = fit(games)

    assert result.strengths["C"].value is None and result.strengths["C"].reason == NO_WINS
    assert result.strengths["C"].component is None
    assert _value(result, "A") == pytest.approx(math.sqrt(3), rel=1e-6)
    assert _value(result, "B") == pytest.approx(1 / math.sqrt(3), rel=1e-6)


def test_a_contestant_that_never_lost_is_unbounded_and_removed() -> None:
    # A beats everyone; B and C split their games.
    games = [*_games("A", "B", 2, 0), *_games("A", "C", 2, 0), *_games("B", "C", 2, 2)]

    result = fit(games)

    assert result.strengths["A"].value is None and result.strengths["A"].reason == NEVER_LOST
    assert _value(result, "B") == pytest.approx(1.0) and _value(result, "C") == pytest.approx(1.0)


def test_a_disconnected_graph_is_fitted_per_component_each_normalized() -> None:
    result = fit([*_games("A", "B", 3, 1), *_games("C", "D", 3, 1)])

    assert result.components == (("A", "B"), ("C", "D"))
    for pair in (("A", "B"), ("C", "D")):
        assert math.prod(_value(result, name) for name in pair) == pytest.approx(1.0, rel=1e-6)
    assert result.strengths["A"].component == 0 and result.strengths["C"].component == 1


def test_inconsistent_counts_as_a_tie_and_invalid_is_excluded() -> None:
    comparisons = [
        Comparison("A", "B", A),
        Comparison("A", "B", PairOutcome.INCONSISTENT),
        Comparison("A", "C", PairOutcome.INVALID),
    ]

    result = fit(comparisons)

    # W_A = 1.5, W_B = 0.5, so the ratio is 3.
    assert _value(result, "A") / _value(result, "B") == pytest.approx(3.0, rel=1e-6)
    assert "C" not in result.strengths  # its only comparison was invalid


def test_all_ties_give_equal_strengths() -> None:
    result = fit([Comparison("A", "B", TIE)] * 4)

    assert _value(result, "A") == pytest.approx(1.0) and _value(result, "B") == pytest.approx(1.0)


def test_no_comparisons_is_an_empty_converged_fit() -> None:
    result = fit([])

    assert result.strengths == {} and result.components == () and result.converged


def test_hitting_the_iteration_cap_warns_and_is_not_converged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(bradley_terry, "MAX_ITERATIONS", 2)

    with caplog.at_level(logging.WARNING):
        result = fit([*_games("A", "B", 5, 2), *_games("B", "C", 4, 3), *_games("A", "C", 6, 1)])

    assert result.converged is False and result.iterations == 2
    assert "2-iteration cap" in caplog.text
