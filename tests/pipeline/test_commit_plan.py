"""Tests for the commit plan types and the template-to-subject map (slice 196 D1)."""

from __future__ import annotations

import pytest

from squadron.pipeline.commit_plan import (
    CommitSubject,
    UnmappedTemplateError,
    subject_for_template,
)


@pytest.mark.parametrize(
    ("template", "subject"),
    [
        ("slice", CommitSubject.DESIGN),
        ("tasks", CommitSubject.TASKS),
        ("code", CommitSubject.CODE),
        ("arch", CommitSubject.ARCHITECTURE),
    ],
)
def test_template_maps_to_subject(template: str, subject: CommitSubject) -> None:
    assert subject_for_template(template) is subject


def test_unmapped_template_raises_naming_the_template() -> None:
    with pytest.raises(UnmappedTemplateError, match="'rules'"):
        subject_for_template("rules")
