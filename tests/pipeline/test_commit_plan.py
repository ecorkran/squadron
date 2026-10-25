"""Tests for the commit plan types, the template-to-subject map and subject path sets."""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.pipeline.commit_plan import (
    CommitSubject,
    CommitTarget,
    UnmappedTemplateError,
    slice_plan_paths,
    subject_for_template,
    subject_paths,
    template_for_subject,
)
from tests.pipeline.commit_fixtures import (
    ARCH_FILE,
    ARCH_REVIEW,
    DESIGN_FILE,
    DESIGN_REVIEW,
    PLAN_FILE,
    SLICE,
    TASKS_FILE,
    TASKS_REVIEW,
    cf_client,
    write_file,
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


@pytest.mark.parametrize(
    "subject",
    [CommitSubject.DESIGN, CommitSubject.TASKS, CommitSubject.ARCHITECTURE, CommitSubject.CODE],
)
def test_template_for_subject_round_trips(subject: CommitSubject) -> None:
    assert subject_for_template(template_for_subject(subject)) is subject


def test_template_for_devlog_raises() -> None:
    with pytest.raises(UnmappedTemplateError, match="devlog"):
        template_for_subject(CommitSubject.DEVLOG)


# ---------------------------------------------------------------------------
# subject_paths
# ---------------------------------------------------------------------------


def _target(subject: CommitSubject, template: str, *, plan: str | None = None) -> CommitTarget:
    slice_index = None if subject is CommitSubject.ARCHITECTURE else SLICE
    return CommitTarget(subject, slice_index, plan, template, 0)


@pytest.mark.parametrize(
    ("subject", "template", "artifact", "review"),
    [
        (CommitSubject.DESIGN, "slice", DESIGN_FILE, DESIGN_REVIEW),
        (CommitSubject.TASKS, "tasks", TASKS_FILE, TASKS_REVIEW),
    ],
)
def test_slice_targets_contain_their_planning_files(
    temp_git_repo: Path, subject: CommitSubject, template: str, artifact: str, review: str
) -> None:
    paths = subject_paths(_target(subject, template), temp_git_repo, cf_client())

    for member in (artifact, review, PLAN_FILE, "DEVLOG.md"):
        assert paths.contains(member), member
    assert not paths.contains("project-documents/user/slices/106-slice.other.md")
    assert not paths.contains("src/app.py")


def test_archived_reviews_are_contained_but_stem_siblings_are_not(temp_git_repo: Path) -> None:
    paths = subject_paths(_target(CommitSubject.DESIGN, "slice"), temp_git_repo, cf_client())
    archive = "project-documents/user/reviews/archive"

    assert paths.contains(f"{archive}/105-review.slice.batch-foo.md")
    assert paths.contains(f"{archive}/105-review.slice.batch-foo.20261025-101500.md")
    assert not paths.contains(f"{archive}/105-review.slice.batch-foobar.md")
    assert not paths.contains(f"{archive}/105-review.slice.batch-foo.txt")


def test_architecture_target_contains_arch_file_review_and_devlog(temp_git_repo: Path) -> None:
    write_file(temp_git_repo, ARCH_FILE, "arch\n")

    paths = subject_paths(
        _target(CommitSubject.ARCHITECTURE, "arch", plan="100"), temp_git_repo, cf_client()
    )

    for member in (ARCH_FILE, ARCH_REVIEW, "DEVLOG.md"):
        assert paths.contains(member), member
    assert not paths.contains(DESIGN_FILE)


def test_slice_plan_paths_contain_the_plan_and_devlog_only(temp_git_repo: Path) -> None:
    write_file(temp_git_repo, PLAN_FILE, "plan\n")

    paths = slice_plan_paths(100, temp_git_repo)

    assert paths.contains(PLAN_FILE)
    assert paths.contains("DEVLOG.md")
    assert not paths.contains(ARCH_FILE)
    assert not paths.contains(DESIGN_FILE)


def test_slice_plan_paths_without_a_plan_file_raise(temp_git_repo: Path) -> None:
    with pytest.raises(FileNotFoundError, match="100-slices"):
        slice_plan_paths(100, temp_git_repo)
