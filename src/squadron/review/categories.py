"""Write-time category normalization for code reviews (slice 402, D3, D4).

The ``code`` template asks for a category from the closed ``ReviewCategory``
vocabulary. What the model actually returns is normalized here. Matching is strict:
the historical alias table (``error-handling`` and friends) is read-side only, so a
prompted model that still emits one of those is recorded as out-of-vocabulary
(``other``, raw string kept) instead of being quietly corrected.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from squadron.core.finding_categories import ReviewCategory
from squadron.review.models import ReviewResult

_logger = logging.getLogger(__name__)

#: Characters stripped from the ends of an emitted category before matching.
_WRAPPING = "`'\" \t"
_SEPARATORS = re.compile(r"[\s_]+")


@dataclass(frozen=True)
class NormalizedCategory:
    """A finding's category after normalization.

    ``category`` is None when the model gave none (never ``other``). ``raw_category`` is
    set only when the emitted string differs from the canonical value.
    """

    category: ReviewCategory | None
    raw_category: str | None


def lenient_category_key(raw: str) -> str:
    """The comparison form of *raw*: trimmed, unwrapped, casefolded, hyphen-separated."""
    return _SEPARATORS.sub("-", raw.strip(_WRAPPING).casefold())


def normalize_category(raw: str | None) -> NormalizedCategory:
    """Normalize one emitted category against ``ReviewCategory``."""
    if raw is None or not raw.strip():
        return NormalizedCategory(None, None)
    members = {member.value: member for member in ReviewCategory}
    exact = members.get(raw)
    if exact is not None:
        return NormalizedCategory(exact, None)
    lenient = members.get(lenient_category_key(raw))
    if lenient is not None:
        return NormalizedCategory(lenient, raw)
    return NormalizedCategory(ReviewCategory.OTHER, raw)


def normalize_result_categories(result: ReviewResult) -> None:
    """Normalize every finding's category in place and mark the result as normalized.

    A missing category stays missing (never ``other``). When the result has findings and
    none carried a ``category:`` tag, the prompt change didn't take: that is logged at
    WARNING and the review is still produced with every category uncategorized.
    """
    emitted = [finding.category for finding in result.findings]
    for finding in result.findings:
        normalized = normalize_category(finding.category)
        finding.category = normalized.category.value if normalized.category is not None else None
        finding.raw_category = normalized.raw_category
    result.categories_normalized = True
    if emitted and all(category is None or not category.strip() for category in emitted):
        _logger.warning(
            "Template '%s' asks for finding categories but none of its %d findings carried one; "
            "every category is uncategorized",
            result.template_name,
            len(emitted),
        )
