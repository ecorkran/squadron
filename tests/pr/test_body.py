"""Tests for the section contract (D4) and the presence-and-filled check (D5)."""

from __future__ import annotations

import pytest

from squadron.pr.assembly import PrFacts
from squadron.pr.body import BodyIncompleteError, check_body_complete, compose_body
from squadron.review.git_utils import CommitRecord
from squadron.review.models import Verdict


def _fixed_composer(response: str):
    async def _compose(prompt: str) -> str:
        return response

    return _compose


# --- compose_body / the section contract (D4) -------------------------------

BODY_COMMITS = (CommitRecord(sha="abc123def456", subject="feat: do the thing"),)


def _full_facts() -> PrFacts:
    return PrFacts(
        commits=BODY_COMMITS,
        slice_design_file="project-documents/user/slices/385-slice.foo.md",
        slice_design_text="# Slice Design: Foo\n\nWhy foo exists.\n",
        checked_items=("did a thing",),
        unchecked_items=("gap remains",),
        review_path="project-documents/user/reviews/385-review.slice.foo.md",
        review_verdict=Verdict.PASS,
        reviewed_sha="deadbeef",
    )


def _no_slice_facts() -> PrFacts:
    return PrFacts(
        commits=BODY_COMMITS,
        slice_design_file=None,
        slice_design_text=None,
        checked_items=(),
        unchecked_items=(),
        review_path=None,
        review_verdict=None,
        reviewed_sha=None,
    )


SECTION_HEADINGS = ("What changed", "Why", "How it was verified", "Known gaps", "Review provenance")


@pytest.mark.asyncio
async def test_full_inputs_produce_five_sections_no_no_input_lines() -> None:
    facts = _full_facts()

    body = await compose_body(facts, compose=_fixed_composer("Some prose."))

    for heading in SECTION_HEADINGS:
        assert f"## {heading}" in body
    assert "No task records for this branch." not in body
    assert "No squadron review covers this branch's commits." not in body


@pytest.mark.asyncio
async def test_what_changed_and_why_prompts_carry_the_designs_own_text() -> None:
    """A model with no tools cannot open the path itself (D3) — naming the
    path in the prompt without its content reliably produces a refusal
    ("I don't have access to your files") instead of prose. The prompt
    must embed the design's own text, not merely point at it.
    """
    facts = PrFacts(
        commits=BODY_COMMITS,
        slice_design_file="project-documents/user/slices/385-slice.foo.md",
        slice_design_text="# Slice Design: Some Slice\n\nThe reason is UNIQUE_MARKER_TEXT.\n",
        checked_items=(),
        unchecked_items=(),
        review_path=None,
        review_verdict=None,
        reviewed_sha=None,
    )
    prompts_seen: list[str] = []

    async def _recording_composer(prompt: str) -> str:
        prompts_seen.append(prompt)
        return "Some prose."

    await compose_body(facts, compose=_recording_composer)

    # First two calls are "what changed" and "why" (has_input=True for both,
    # in section order); the marker text must reach both prompts verbatim.
    assert any("UNIQUE_MARKER_TEXT" in prompt for prompt in prompts_seen[:2])
    assert all("UNIQUE_MARKER_TEXT" in prompt for prompt in prompts_seen[:2])


@pytest.mark.asyncio
async def test_no_slice_the_two_task_sections_carry_the_no_input_line() -> None:
    facts = _no_slice_facts()

    body = await compose_body(facts, compose=_fixed_composer("Some prose."))

    assert body.count("No task records for this branch.") == 2


@pytest.mark.asyncio
async def test_no_review_provenance_carries_its_no_input_line() -> None:
    facts = _no_slice_facts()

    body = await compose_body(facts, compose=_fixed_composer("Some prose."))

    assert "No squadron review covers this branch's commits." in body


@pytest.mark.asyncio
async def test_unplanned_repository_has_five_sections_three_no_input_lines() -> None:
    facts = _no_slice_facts()

    body = await compose_body(facts, compose=_fixed_composer("Some prose."))

    for heading in SECTION_HEADINGS:
        assert f"## {heading}" in body
    assert body.count("No task records for this branch.") == 2
    assert body.count("No squadron review covers this branch's commits.") == 1


@pytest.mark.asyncio
async def test_deterministic_facts_appear_verbatim() -> None:
    facts = _full_facts()

    body = await compose_body(facts, compose=_fixed_composer("Some prose."))

    assert facts.commits[0].sha[:12] in body
    assert facts.slice_design_file is not None
    assert facts.slice_design_file in body
    assert facts.reviewed_sha is not None
    assert facts.reviewed_sha in body


@pytest.mark.asyncio
async def test_model_headings_do_not_duplicate_or_reorder_sections() -> None:
    facts = _full_facts()
    model_response_with_headings = "## What changed\nBogus model heading.\n## Why\nMore bogus text."

    body = await compose_body(facts, compose=_fixed_composer(model_response_with_headings))

    for heading in SECTION_HEADINGS:
        assert body.count(f"## {heading}") == 1


@pytest.mark.asyncio
async def test_only_heading_syntax_outside_fences_is_stripped() -> None:
    """A ``#`` line that is not a heading — or sits in a code fence — survives."""
    model_response = (
        "# A model heading\n"
        "Fixes #123 as described.\n"
        "#123 is the issue.\n"
        "```sh\n"
        "# install first\n"
        "## not a heading either\n"
        "uv sync\n"
        "```\n"
        "### Another model heading"
    )

    body = await compose_body(_full_facts(), compose=_fixed_composer(model_response))

    assert "# install first\n## not a heading either\nuv sync" in body
    assert "#123 is the issue." in body
    assert "A model heading" not in body
    assert "Another model heading" not in body


@pytest.mark.asyncio
async def test_the_provenance_block_renders_the_verdicts_value() -> None:
    body = await compose_body(_full_facts(), compose=_fixed_composer("Some prose."))

    assert "(verdict: PASS, sha: deadbeef)" in body


# --- check_body_complete (D5) -----------------------------------------------


@pytest.mark.asyncio
async def test_complete_body_passes() -> None:
    facts = _full_facts()
    body = await compose_body(facts, compose=_fixed_composer("Some prose."))

    check_body_complete(body, facts)  # must not raise


@pytest.mark.asyncio
async def test_body_missing_one_section_fails_naming_it() -> None:
    facts = _full_facts()
    body = await compose_body(facts, compose=_fixed_composer("Some prose."))
    body_missing_why = body.replace("## Why", "## Renamed Section")

    with pytest.raises(BodyIncompleteError) as exc_info:
        check_body_complete(body_missing_why, facts)

    assert "Why" in str(exc_info.value)


@pytest.mark.asyncio
async def test_section_containing_only_the_heading_fails() -> None:
    facts = _full_facts()
    body = (
        "## What changed\n\n## Why\n\n"
        "## How it was verified\n\n## Known gaps\n\n## Review provenance\n\n"
    )

    with pytest.raises(BodyIncompleteError):
        check_body_complete(body, facts)


@pytest.mark.asyncio
async def test_section_containing_only_whitespace_fails() -> None:
    facts = _full_facts()
    body = (
        "## What changed\n   \n\n## Why\n\n"
        "## How it was verified\n\n## Known gaps\n\n## Review provenance\n\n"
    )

    with pytest.raises(BodyIncompleteError):
        check_body_complete(body, facts)


@pytest.mark.asyncio
async def test_section_containing_exactly_its_no_input_line_passes() -> None:
    facts = _no_slice_facts()
    body = await compose_body(facts, compose=_fixed_composer("Some prose."))

    check_body_complete(body, facts)  # must not raise


def test_sections_present_but_out_of_order_fails() -> None:
    facts = _full_facts()
    body = (
        "## Why\n\nSome prose about why.\n\n"
        "## What changed\n\nSome prose about what changed.\n\n"
        "## How it was verified\n\nprose\n\n"
        "## Known gaps\n\nprose\n\n"
        "## Review provenance\n\nprose\n\n"
    )

    with pytest.raises(BodyIncompleteError):
        check_body_complete(body, facts)


@pytest.mark.asyncio
async def test_check_raises_rather_than_returning_a_falsy_result() -> None:
    """The failure path is a raise, never a return value a caller could ignore
    and proceed to create the PR anyway — this is what makes "no host call on
    failure" true of every caller by construction, not by caller discipline.
    """
    facts = _full_facts()
    body = await compose_body(facts, compose=_fixed_composer("Some prose."))
    body_missing_why = body.replace("## Why", "## Renamed Section")

    with pytest.raises(BodyIncompleteError):
        check_body_complete(body_missing_why, facts)
