from __future__ import annotations

import pytest

from squadron.pr.branch import parse_slice_branch


@pytest.mark.parametrize(
    ("branch", "expected"),
    [
        ("385-slice.create-a-pr-with-a-good-message", 385),
        ("384-slice.post-findings-to-the-pr", 384),
        ("squadron-pr", None),
        ("main", None),
        ("feature/add-thing", None),
        ("123-review-something", None),
        ("910-slice.foo.bar", 910),
    ],
)
def test_parse_slice_branch(branch: str, expected: int | None) -> None:
    assert parse_slice_branch(branch) == expected
