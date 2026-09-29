"""Tests for review part naming and the worst-verdict fold."""

from __future__ import annotations

import itertools

import pytest

from squadron.review.models import Verdict
from squadron.review.parts import ReviewPart, review_parts, worst_verdict

_ORDER = [Verdict.PASS, Verdict.CONCERNS, Verdict.FAIL, Verdict.UNKNOWN]


class TestReviewParts:
    def test_single_path_is_unsuffixed(self) -> None:
        assert review_parts(["a.md"]) == [ReviewPart("a.md", None)]

    def test_multiple_paths_are_numbered_in_order(self) -> None:
        parts = review_parts(["a-1.md", "a-2.md", "a-3.md"])
        assert parts == [
            ReviewPart("a-1.md", "part-1"),
            ReviewPart("a-2.md", "part-2"),
            ReviewPart("a-3.md", "part-3"),
        ]

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="no input paths"):
            review_parts([])


class TestWorstVerdict:
    @pytest.mark.parametrize(("first", "second"), list(itertools.permutations(_ORDER, 2)))
    def test_every_ordered_pair(self, first: Verdict, second: Verdict) -> None:
        expected = max(first, second, key=_ORDER.index)
        assert worst_verdict([str(first), str(second)]) == expected

    @pytest.mark.parametrize("verdict", _ORDER)
    def test_single_value(self, verdict: Verdict) -> None:
        assert worst_verdict([str(verdict)]) == verdict

    def test_all_unknown(self) -> None:
        assert worst_verdict(["UNKNOWN", "UNKNOWN"]) == "UNKNOWN"

    def test_unknown_outranks_pass(self) -> None:
        assert worst_verdict(["PASS", "UNKNOWN"]) == "UNKNOWN"

    def test_accepts_enum_members(self) -> None:
        assert worst_verdict([Verdict.PASS, Verdict.FAIL]) == Verdict.FAIL

    def test_tie_returns_first_occurrence(self) -> None:
        first, second = Verdict.CONCERNS, "CONCERNS"
        assert worst_verdict(["PASS", first, second]) is first

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="no verdicts"):
            worst_verdict([])

    def test_unknown_string_raises(self) -> None:
        with pytest.raises(ValueError):
            worst_verdict(["PASS", "MAYBE"])
