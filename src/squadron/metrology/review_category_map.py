"""Read-side category map for code reviews written before slice 402 (D7).

Historical reviews carry whatever category string the model chose. This fixed table maps
the frequent ones whose meaning clearly matches a ``ReviewCategory`` value; every other
string becomes ``other`` with the raw string kept. It is applied only at ingest, never at
write time (D4), and every record built through it is marked ``read_side_mapped``. The
table can grow without a migration, because ingest re-derives every record.

An entry exists only for a string with four or more findings in the corpus counted on
20261023. ``style`` and ``code-quality`` are deliberately absent (they go to ``other``).
"""

from __future__ import annotations

from squadron.core.finding_categories import ReviewCategory
from squadron.review.categories import NormalizedCategory, lenient_category_key

#: The sentinel the review frontmatter writes for a finding with no category.
UNCATEGORIZED = "uncategorized"

_ROWS: dict[ReviewCategory, tuple[str, ...]] = {
    ReviewCategory.ERROR_HANDLING_OBSERVABILITY: ("error-handling", "observability"),
    ReviewCategory.TEST_DEBT: ("testing", "test-coverage"),
    ReviewCategory.ARCHITECTURAL_DECAY: ("design", "design-principles", "structure"),
    ReviewCategory.CONSISTENCY_ROT: ("dry", "project-conventions", "consistency"),
    ReviewCategory.TYPE_CONTRACT_DEBT: ("typing",),
    ReviewCategory.PERFORMANCE_RESOURCE: ("performance",),
    ReviewCategory.SECURITY_HYGIENE: ("security",),
    ReviewCategory.DOCUMENTATION_DRIFT: ("documentation",),
    ReviewCategory.CORRECTNESS: ("correctness", "concurrency"),
}

#: Historical string (already in lenient form) to category.
HISTORICAL_CATEGORIES: dict[str, ReviewCategory] = {
    historical: member for member, strings in _ROWS.items() for historical in strings
}


def map_historical_category(raw: str | None) -> NormalizedCategory:
    """Map one historical category string; a missing or ``uncategorized`` one stays missing."""
    if raw is None or not raw.strip():
        return NormalizedCategory(None, None)
    key = lenient_category_key(raw)
    if key == UNCATEGORIZED:
        return NormalizedCategory(None, None)
    member = HISTORICAL_CATEGORIES.get(key)
    if member is None:
        return NormalizedCategory(ReviewCategory.OTHER, raw)
    return NormalizedCategory(member, None if raw == member.value else raw)
