"""The read-side category map for historical code reviews (slice 402, D7)."""

from __future__ import annotations

import pytest

from squadron.core.finding_categories import ReviewCategory
from squadron.metrology.review_category_map import HISTORICAL_CATEGORIES, map_historical_category
from squadron.review.categories import lenient_category_key

D7_TABLE = {
    "error-handling": ReviewCategory.ERROR_HANDLING_OBSERVABILITY,
    "observability": ReviewCategory.ERROR_HANDLING_OBSERVABILITY,
    "testing": ReviewCategory.TEST_DEBT,
    "test-coverage": ReviewCategory.TEST_DEBT,
    "design": ReviewCategory.ARCHITECTURAL_DECAY,
    "design-principles": ReviewCategory.ARCHITECTURAL_DECAY,
    "structure": ReviewCategory.ARCHITECTURAL_DECAY,
    "dry": ReviewCategory.CONSISTENCY_ROT,
    "project-conventions": ReviewCategory.CONSISTENCY_ROT,
    "consistency": ReviewCategory.CONSISTENCY_ROT,
    "typing": ReviewCategory.TYPE_CONTRACT_DEBT,
    "performance": ReviewCategory.PERFORMANCE_RESOURCE,
    "security": ReviewCategory.SECURITY_HYGIENE,
    "documentation": ReviewCategory.DOCUMENTATION_DRIFT,
    "correctness": ReviewCategory.CORRECTNESS,
    "concurrency": ReviewCategory.CORRECTNESS,
}


def test_the_table_is_exactly_the_d7_rows() -> None:
    assert HISTORICAL_CATEGORIES == D7_TABLE
    assert len(HISTORICAL_CATEGORIES) == 16


@pytest.mark.parametrize(("raw", "expected"), list(D7_TABLE.items()))
def test_every_d7_string_maps_and_keeps_the_raw_string_when_it_differs(
    raw: str, expected: ReviewCategory
) -> None:
    result = map_historical_category(raw)

    assert result.category is expected
    assert result.raw_category == (None if raw == expected.value else raw)


def test_the_lenient_key_applies() -> None:
    result = map_historical_category("Error Handling")

    assert result.category is ReviewCategory.ERROR_HANDLING_OBSERVABILITY
    assert result.raw_category == "Error Handling"


@pytest.mark.parametrize("raw", [None, "", "uncategorized", "Uncategorized"])
def test_missing_and_uncategorized_stay_missing(raw: str | None) -> None:
    result = map_historical_category(raw)

    assert result.category is None
    assert result.raw_category is None


@pytest.mark.parametrize("raw", ["style", "code-quality", "naming", "design/typing"])
def test_everything_else_is_other_with_the_raw_string_kept(raw: str) -> None:
    result = map_historical_category(raw)

    assert result.category is ReviewCategory.OTHER
    assert result.raw_category == raw


def test_table_values_are_members_and_keys_are_in_lenient_form() -> None:
    for key, member in HISTORICAL_CATEGORIES.items():
        assert isinstance(member, ReviewCategory)
        assert lenient_category_key(key) == key
