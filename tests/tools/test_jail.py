"""Tests for the path jail rule in isolation.

Tasks 4.2 and 5.2 exercise the jail end-to-end through the file tools. This module pins the
rule itself, so a jail regression names the jail rather than surfacing as two confusing
tool-test failures.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from squadron.tools.builtin import _resolve_in_jail, contained_in_jail
from squadron.tools.builtin._shared import jail_violation
from squadron.tools.models import JailSpec


@pytest.mark.parametrize(
    "path",
    [
        "file.txt",
        "sub/nested/file.txt",
        "sub/../file.txt",
        "./file.txt",
    ],
)
def test_relative_paths_inside_the_jail_are_accepted(tmp_path: Path, path: str) -> None:
    assert _resolve_in_jail(JailSpec(root=tmp_path), path) == (tmp_path / path).resolve(strict=False)


def test_absolute_path_inside_the_jail_is_accepted(tmp_path: Path) -> None:
    target = tmp_path / "sub" / "file.txt"

    assert _resolve_in_jail(JailSpec(root=tmp_path), str(target)) == target.resolve(strict=False)


def test_jail_root_itself_is_accepted(tmp_path: Path) -> None:
    assert _resolve_in_jail(JailSpec(root=tmp_path), ".") == tmp_path


@pytest.mark.parametrize("path", ["../escape", "../../../escape", "sub/../../escape"])
def test_upward_traversal_is_rejected(tmp_path: Path, path: str) -> None:
    jail = tmp_path / "jail"
    jail.mkdir()

    assert _resolve_in_jail(JailSpec(root=jail), path) is None


def test_absolute_path_outside_the_jail_is_rejected(tmp_path: Path) -> None:
    jail = tmp_path / "jail"
    jail.mkdir()
    outside = tmp_path / "outside" / "file.txt"

    assert _resolve_in_jail(JailSpec(root=jail), str(outside)) is None


def test_symlink_pointing_outside_the_jail_is_rejected(tmp_path: Path) -> None:
    jail = tmp_path / "jail"
    jail.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("secret")
    (jail / "link").symlink_to(outside)

    assert _resolve_in_jail(JailSpec(root=jail), "link/secret.txt") is None


def test_path_whose_parent_resolves_outside_the_jail_is_rejected(tmp_path: Path) -> None:
    """write_file relies on this before creating parent directories."""
    jail = tmp_path / "jail"
    jail.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (jail / "link").symlink_to(outside)

    candidate = _resolve_in_jail(JailSpec(root=jail), "link/new.txt")

    assert candidate is None


def test_sibling_directory_sharing_a_string_prefix_is_rejected(tmp_path: Path) -> None:
    """Regression test for the 'do not use startswith' rule.

    ``/tmp/.../jail_evil`` starts with ``/tmp/.../jail`` as a string but is not inside it.
    Prefix comparison accepts it; ``is_relative_to`` correctly rejects it.
    """
    jail = tmp_path / "jail"
    jail.mkdir()
    evil = tmp_path / "jail_evil"
    evil.mkdir()
    (evil / "file.txt").write_text("nope")

    assert str(evil).startswith(str(jail))  # the trap the rule avoids
    assert _resolve_in_jail(JailSpec(root=jail), str(evil / "file.txt")) is None


# --- Exclusions (slice 918, #94) -------------------------------------------------------
#
# An exclusion is a path inside the jail that is nonetheless refused. It exists because a
# document review's own predecessors sit inside the tool jail under the document's name
# prefix, so the review reads and re-grades them. These tests pin the predicate; the
# end-to-end behavior is in test_jail_exclusions.py.


def _jail_with_reviews(tmp_path: Path) -> tuple[JailSpec, Path]:
    """Build a jail containing an excluded ``reviews/`` directory and return both."""
    reviews = tmp_path / "docs" / "reviews"
    reviews.mkdir(parents=True)
    return JailSpec(root=tmp_path, excluded=(reviews.resolve(),)), reviews


def test_path_inside_an_excluded_directory_is_refused(tmp_path: Path) -> None:
    spec, reviews = _jail_with_reviews(tmp_path)
    (reviews / "380-review.arch.md").write_text("stale finding")

    assert _resolve_in_jail(spec, "docs/reviews/380-review.arch.md") is None
    assert not contained_in_jail(spec, reviews / "380-review.arch.md", tool="list_files")


def test_nested_path_under_an_excluded_directory_is_refused(tmp_path: Path) -> None:
    """Archived predecessors live one level deeper; the exclusion must reach them."""
    spec, reviews = _jail_with_reviews(tmp_path)
    archive = reviews / "archive"
    archive.mkdir()
    (archive / "380-review.arch.md").write_text("two revisions ago")

    assert _resolve_in_jail(spec, "docs/reviews/archive/380-review.arch.md") is None
    assert not contained_in_jail(spec, archive / "380-review.arch.md", tool="grep")


def test_the_excluded_directory_itself_is_refused(tmp_path: Path) -> None:
    spec, reviews = _jail_with_reviews(tmp_path)

    assert _resolve_in_jail(spec, "docs/reviews") is None
    assert not contained_in_jail(spec, reviews, tool="list_files")


def test_path_inside_the_jail_but_outside_every_exclusion_still_resolves(tmp_path: Path) -> None:
    spec, _ = _jail_with_reviews(tmp_path)
    target = tmp_path / "docs" / "380-arch.md"

    assert _resolve_in_jail(spec, "docs/380-arch.md") == target.resolve(strict=False)
    assert contained_in_jail(spec, target, tool="read_file")


@pytest.mark.parametrize("path", ["file.txt", "sub/nested/file.txt", "../escape"])
def test_an_empty_exclusion_set_behaves_identically_to_no_exclusions(tmp_path: Path, path: str) -> None:
    """The default-path regression guard named in the design's Risks section."""
    jail = tmp_path / "jail"
    jail.mkdir()
    bare = JailSpec(root=jail)
    explicit = JailSpec(root=jail, excluded=())

    assert _resolve_in_jail(bare, path) == _resolve_in_jail(explicit, path)
    entry = (jail / path).resolve(strict=False)
    assert contained_in_jail(bare, entry, tool="read_file") == contained_in_jail(
        explicit, entry, tool="read_file"
    )


def test_sibling_sharing_a_prefix_with_an_excluded_directory_is_not_excluded(
    tmp_path: Path,
) -> None:
    """The ``is_relative_to`` assertion for exclusions.

    ``reviews-archive`` starts with ``reviews`` as a string but is a different directory.
    A ``str.startswith`` implementation of the exclusion match fails this test.
    """
    reviews = tmp_path / "reviews"
    reviews.mkdir()
    sibling = tmp_path / "reviews-archive"
    sibling.mkdir()
    (sibling / "notes.md").write_text("keep me")
    spec = JailSpec(root=tmp_path, excluded=(reviews.resolve(),))

    assert str(sibling).startswith(str(reviews))  # the trap the rule avoids
    target = sibling / "notes.md"
    assert _resolve_in_jail(spec, "reviews-archive/notes.md") == target.resolve(strict=False)
    assert contained_in_jail(spec, target, tool="read_file")


def test_resolve_in_jail_does_not_log_its_own_refusals(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Refusals are worded and logged in exactly one place: ``jail_violation``.

    The predicate logging as well would double every refusal, and the two records disagreed
    — the predicate called it an exclusion while ``jail_violation`` called it a jail escape.
    """
    spec, _ = _jail_with_reviews(tmp_path)

    with caplog.at_level(logging.WARNING):
        _resolve_in_jail(spec, "docs/reviews/380-review.arch.md")
        _resolve_in_jail(spec, "../escape")

    assert [r for r in caplog.records if r.levelno == logging.WARNING] == []


def test_an_exclusion_refusal_emits_exactly_one_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    spec, _ = _jail_with_reviews(tmp_path)

    with caplog.at_level(logging.WARNING):
        jail_violation("read_file", spec, "docs/reviews/380-review.arch.md")

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "excluded" in warnings[0].getMessage()


def test_an_exclusion_refusal_tells_the_model_only_that_the_file_is_absent(
    tmp_path: Path,
) -> None:
    """Design D6. The operator log says "excluded"; the model is told "not found".

    Anything more specific both invites probing for the boundary and, since review
    artifacts are named after the document under review, confirms the predecessors exist.
    """
    spec, reviews = _jail_with_reviews(tmp_path)
    target = reviews / "380-review.arch.md"

    result = jail_violation("read_file", spec, "docs/reviews/380-review.arch.md")

    assert result.is_error
    assert result.content == f"Error: file not found: {target}"
    assert "exclud" not in result.content.lower()


def test_a_jail_escape_still_reports_the_trust_boundary(tmp_path: Path) -> None:
    """The escape message is unchanged: a path genuinely outside the jail is named as such.

    An exclusion is a legitimate path deliberately withheld; an escape is a reach past the
    trust boundary. Collapsing the two would hide the one that matters.
    """
    spec, _ = _jail_with_reviews(tmp_path)

    result = jail_violation("read_file", spec, "../escape")

    assert result.is_error
    assert "outside the working directory" in result.content


def test_an_exclusion_refusal_is_worded_distinguishably_from_a_jail_escape(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """An operator reading a log must be able to tell the two refusals apart."""
    spec, reviews = _jail_with_reviews(tmp_path)
    outside = tmp_path.parent / "outside"

    with caplog.at_level(logging.WARNING):
        contained_in_jail(spec, reviews / "380-review.arch.md", tool="list_files")
        contained_in_jail(spec, outside, tool="list_files")

    messages = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert len(messages) == 2
    assert "excluded" in messages[0] and "jail escape" not in messages[0]
    assert "jail escape" in messages[1] and "excluded" not in messages[1]
