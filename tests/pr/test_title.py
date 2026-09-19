"""Tests for title resolution (D4a)."""

from __future__ import annotations

import pytest

from squadron.pr.title import resolve_title
from squadron.review.git_utils import CommitRecord

TITLE_COMMITS = (
    CommitRecord(sha="def456", subject="feat: second commit"),
    CommitRecord(sha="abc123", subject="feat: first commit"),
)


class _FailIfCalledComposer:
    """A composer that fails the test if the model is ever asked."""

    async def __call__(self, prompt: str) -> str:
        raise AssertionError("the model must not be called")


def _fixed_composer(response: str):
    async def _compose(prompt: str) -> str:
        return response

    return _compose


@pytest.mark.asyncio
async def test_title_flag_wins_over_both_other_terms() -> None:
    design_text = "# Slice Design: Some Slice\n"

    title = await resolve_title(
        title_flag="Custom Title",
        design_text=design_text,
        commits=TITLE_COMMITS,
        compose=_FailIfCalledComposer(),
    )

    assert title == "Custom Title"


@pytest.mark.asyncio
async def test_resolved_slice_branch_uses_h1_and_never_calls_the_composer() -> None:
    design_text = "# Slice Design: Create a PR with a Good Message\n\nBody text.\n"

    title = await resolve_title(
        title_flag=None,
        design_text=design_text,
        commits=TITLE_COMMITS,
        compose=_FailIfCalledComposer(),
    )

    assert title == "Create a PR with a Good Message"


@pytest.mark.asyncio
async def test_design_with_non_matching_h1_falls_through_to_the_model() -> None:
    design_text = "# Something Else Entirely\n"

    title = await resolve_title(
        title_flag=None,
        design_text=design_text,
        commits=TITLE_COMMITS,
        compose=_fixed_composer("A composed title"),
    )

    assert title == "A composed title"


@pytest.mark.asyncio
async def test_non_slice_branch_composes() -> None:
    title = await resolve_title(
        title_flag=None,
        design_text=None,
        commits=TITLE_COMMITS,
        compose=_fixed_composer("A composed title"),
    )

    assert title == "A composed title"


@pytest.mark.asyncio
async def test_empty_model_response_falls_back_to_first_commit_subject() -> None:
    title = await resolve_title(
        title_flag=None,
        design_text=None,
        commits=TITLE_COMMITS,
        compose=_fixed_composer("   "),
    )

    assert title == TITLE_COMMITS[0].subject


@pytest.mark.asyncio
async def test_multiline_response_falls_back() -> None:
    title = await resolve_title(
        title_flag=None,
        design_text=None,
        commits=TITLE_COMMITS,
        compose=_fixed_composer("line one\nline two"),
    )

    assert title == TITLE_COMMITS[0].subject


@pytest.mark.asyncio
async def test_response_over_72_characters_falls_back() -> None:
    long_response = "x" * 100
    title = await resolve_title(
        title_flag=None,
        design_text=None,
        commits=TITLE_COMMITS,
        compose=_fixed_composer(long_response),
    )

    assert title == TITLE_COMMITS[0].subject


@pytest.mark.asyncio
async def test_valid_60_character_response_is_used() -> None:
    valid_response = "y" * 60
    title = await resolve_title(
        title_flag=None,
        design_text=None,
        commits=TITLE_COMMITS,
        compose=_fixed_composer(valid_response),
    )

    assert title == valid_response
