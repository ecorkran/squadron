"""Tests for the gate action's reduction core: severity table and reduce_verdicts."""

from __future__ import annotations

import pytest

from squadron.pipeline.actions.gate import reduce_verdicts

_VERDICTS = ["PASS", "CONCERNS", "FAIL", "UNKNOWN"]

_MOST_SEVERE = {"PASS": 0, "CONCERNS": 1, "FAIL": 2, "UNKNOWN": 3}


def _expected(a: str, b: str) -> str:
    return a if _MOST_SEVERE[a] >= _MOST_SEVERE[b] else b


class TestReduceVerdictsCrossProduct:
    """Full 4x4 cross-product of {PASS, CONCERNS, FAIL, UNKNOWN}, incl. diagonal ties."""

    @pytest.mark.parametrize(
        ("a", "b"),
        [(a, b) for a in _VERDICTS for b in _VERDICTS],
    )
    def test_most_severe_wins(self, a: str, b: str) -> None:
        assert reduce_verdicts(a, b) == _expected(a, b)

    @pytest.mark.parametrize("verdict", _VERDICTS)
    def test_diagonal_ties_are_idempotent(self, verdict: str) -> None:
        assert reduce_verdicts(verdict, verdict) == verdict


class TestReduceVerdictsNoneNormalization:
    """A None leg normalizes to UNKNOWN before ranking (F001, fail-closed)."""

    def test_none_and_pass_yields_unknown(self) -> None:
        assert reduce_verdicts(None, "PASS") == "UNKNOWN"

    def test_pass_and_none_yields_unknown(self) -> None:
        assert reduce_verdicts("PASS", None) == "UNKNOWN"

    def test_none_and_none_yields_unknown(self) -> None:
        assert reduce_verdicts(None, None) == "UNKNOWN"

    @pytest.mark.parametrize("verdict", _VERDICTS)
    def test_none_dominates_every_verdict(self, verdict: str) -> None:
        assert reduce_verdicts(None, verdict) == "UNKNOWN"
        assert reduce_verdicts(verdict, None) == "UNKNOWN"
