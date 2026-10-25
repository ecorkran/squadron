"""Write-time category normalization (slice 402, D4)."""

from __future__ import annotations

import pytest

from squadron.core.finding_categories import ReviewCategory
from squadron.review.categories import lenient_category_key, normalize_category


@pytest.mark.parametrize("raw", [None, "", "   "])
def test_missing_category_stays_missing_never_other(raw: str | None) -> None:
    result = normalize_category(raw)

    assert result.category is None
    assert result.raw_category is None


@pytest.mark.parametrize("member", list(ReviewCategory))
def test_canonical_value_keeps_no_raw_string(member: ReviewCategory) -> None:
    result = normalize_category(member.value)

    assert result.category is member
    assert result.raw_category is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("`Correctness`", ReviewCategory.CORRECTNESS),
        ("Test Debt", ReviewCategory.TEST_DEBT),
        ("test_debt", ReviewCategory.TEST_DEBT),
        ('"security-hygiene"', ReviewCategory.SECURITY_HYGIENE),
        ("  Error-Handling-Observability ", ReviewCategory.ERROR_HANDLING_OBSERVABILITY),
    ],
)
def test_lenient_match_maps_and_keeps_the_string_as_emitted(raw: str, expected: ReviewCategory) -> None:
    result = normalize_category(raw)

    assert result.category is expected
    assert result.raw_category == raw


@pytest.mark.parametrize("raw", ["error-handling", "design/typing", "testing", "style"])
def test_historical_aliases_are_out_of_vocabulary_at_write_time(raw: str) -> None:
    result = normalize_category(raw)

    assert result.category is ReviewCategory.OTHER
    assert result.raw_category == raw


def test_lenient_key_is_the_public_comparison_form() -> None:
    assert lenient_category_key(" `Error_Handling` ") == "error-handling"
