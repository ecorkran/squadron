"""Tests for assemble_facts — every field copied, none inferred."""

from __future__ import annotations

from pathlib import Path

from squadron.pr.assembly import assemble_facts
from squadron.pr.inputs import PrInputs, ReviewProvenance, SliceInputs
from squadron.pr.tasks import TaskItems
from squadron.review.git_utils import CommitRecord
from squadron.review.models import Verdict

COMMITS = (CommitRecord(sha="abc123", subject="feat: do the thing"),)


def test_full_inputs_populate_every_field() -> None:
    inputs = PrInputs(
        commits=COMMITS,
        slice=SliceInputs(
            index=385,
            design_file="project-documents/user/slices/385-slice.foo.md",
            task_items=TaskItems(checked=("done",), unchecked=("not done",)),
        ),
    )
    review = ReviewProvenance(
        path=Path("project-documents/user/reviews/385-review.slice.foo.md"),
        verdict=Verdict.PASS,
        reviewed_sha="deadbeef",
    )

    facts = assemble_facts(inputs, review)

    assert facts.commits == COMMITS
    assert facts.slice_design_file == "project-documents/user/slices/385-slice.foo.md"
    assert facts.checked_items == ("done",)
    assert facts.unchecked_items == ("not done",)
    assert facts.review_path == "project-documents/user/reviews/385-review.slice.foo.md"
    assert facts.review_verdict == Verdict.PASS
    assert facts.reviewed_sha == "deadbeef"


def test_no_slice_leaves_slice_fields_absent_but_commits_present() -> None:
    inputs = PrInputs(
        commits=COMMITS,
        slice=SliceInputs(index=None, design_file=None, task_items=None),
    )

    facts = assemble_facts(inputs, review=None)

    assert facts.commits == COMMITS
    assert facts.slice_design_file is None
    assert facts.checked_items == ()
    assert facts.unchecked_items == ()


def test_no_review_leaves_review_fields_absent() -> None:
    inputs = PrInputs(
        commits=COMMITS,
        slice=SliceInputs(index=385, design_file="path/to/design.md", task_items=None),
    )

    facts = assemble_facts(inputs, review=None)

    assert facts.review_path is None
    assert facts.review_verdict is None
    assert facts.reviewed_sha is None


def test_no_task_items_both_tuples_empty() -> None:
    inputs = PrInputs(
        commits=COMMITS,
        slice=SliceInputs(index=385, design_file="path/to/design.md", task_items=None),
    )

    facts = assemble_facts(inputs, review=None)

    assert facts.checked_items == ()
    assert facts.unchecked_items == ()


def test_no_field_is_ever_a_placeholder_string() -> None:
    inputs = PrInputs(
        commits=COMMITS,
        slice=SliceInputs(index=None, design_file=None, task_items=None),
    )

    facts = assemble_facts(inputs, review=None)

    for value in (facts.slice_design_file, facts.review_path, facts.reviewed_sha):
        assert value is None or value.strip()
        if value is not None:
            assert "unknown" not in value.lower()
            assert "n/a" not in value.lower()
