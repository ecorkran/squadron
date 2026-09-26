"""Slice consumers never match a PR review, and target-agnostic ones still work.

Two glob families read the reviews directory, and 383 puts a differently-named
artifact in it for the first time (D4).

``{index}-review.*`` consumers cannot match a PR artifact **by construction**:
``locate_review`` builds its pattern from an ``int``, and metrology capture
guards with ``target.isdigit()`` before globbing. Any non-numeric stem — the
``pr-`` forms from slice 926 or the older ``github.com-`` form — cannot
satisfy either. That is a property of how the globs are
built rather than a convention anyone follows, so these tests pin it — the
failure they guard against is a future refactor that starts building the
pattern from a string.

``*-review.*`` consumers do match, and classify by reading ``targetKind`` from
frontmatter rather than parsing the filename.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.metrology.capture import MetrologyTargetError, resolve_target
from squadron.metrology.identity import read_review_frontmatter
from squadron.review.persistence import REVIEWS_DIR
from squadron.review.resolution_evidence import ResolutionError, locate_review

_SLICE_REVIEW = """---
docType: review
layer: project
reviewType: code
slice: some-slice
targetKind: slice
rulesSource: project
project: squadron
verdict: PASS
sourceDocument: project-documents/user/slices/42-slice.md
aiModel: claude-opus-4-5
status: complete
dateCreated: 20260401
dateUpdated: 20260401
---

# Review: code — slice 42

No specific findings.
"""

_PR_REVIEW = """---
docType: review
layer: project
reviewType: code
pr:
  host: github.com
  owner: ecorkran
  repository: squadron
  number: 42
  url: https://github.com/ecorkran/squadron/pull/42
targetKind: pr
rulesSource: project
project: squadron
verdict: PASS
sourceDocument: https://github.com/ecorkran/squadron/pull/42
aiModel: claude-opus-4-5
status: complete
dateCreated: 20260401
dateUpdated: 20260401
---

# Review: code — PR #42

No specific findings.
"""

#: The collision this whole file exists to test: PR 42 and slice 42, one
#: directory. Nothing prevents an operator from having both.
_SLICE_NAME = "42-review.code.some-slice.md"

#: Every PR artifact name a reviews directory can hold. The ``github.com-`` form
#: predates slice 926 and stays on purpose: old-name artifacts are never migrated
#: (926, D6), so they must keep being ignored alongside the ``pr-`` forms.
_PR_NAMES = [
    "github.com-ecorkran-squadron-42-review.code.md",
    "pr-42-review.code.md",
    "pr-42-review.code.ecorkran-squadron.md",
]


@pytest.fixture(params=_PR_NAMES)
def pr_name(request: pytest.FixtureRequest) -> str:
    return request.param


@pytest.fixture
def both_reviews(tmp_path: Path, pr_name: str) -> Path:
    reviews = tmp_path / REVIEWS_DIR
    reviews.mkdir(parents=True)
    (reviews / _SLICE_NAME).write_text(_SLICE_REVIEW, encoding="utf-8")
    (reviews / pr_name).write_text(_PR_REVIEW, encoding="utf-8")
    return tmp_path


class TestResolveSelectsTheSliceReview:
    def test_locate_review_finds_the_slice_not_the_pr(self, both_reviews: Path) -> None:
        """``sq review resolve 42`` with both present."""
        found = locate_review(42, None, str(both_reviews))

        assert found.name == _SLICE_NAME

    def test_it_is_unambiguous_despite_two_code_reviews_of_42(self, both_reviews: Path) -> None:
        """The PR artifact does not even register as a competing candidate.

        ``locate_review`` raises on an ambiguous index. If the PR review could
        match, this call would raise instead of resolving — so a passing
        assertion here is the proof that the glob excludes it, not merely that
        the slice sorted first.
        """
        found = locate_review(42, "code", str(both_reviews))

        assert found.name == _SLICE_NAME

    def test_the_pr_review_is_unreachable_by_index_at_all(self, both_reviews: Path) -> None:
        """No index resolves to it, including the PR's own number."""
        (both_reviews / REVIEWS_DIR / _SLICE_NAME).unlink()

        with pytest.raises(ResolutionError):
            locate_review(42, None, str(both_reviews))


class TestMetrologyCaptureSelectsTheSliceReview:
    def test_capture_for_index_42_finds_the_slice_not_the_pr(self, both_reviews: Path) -> None:
        resolved = resolve_target("42", None, str(both_reviews))

        assert resolved.name == _SLICE_NAME

    def test_capture_rejects_a_pr_key_as_a_target(self, both_reviews: Path) -> None:
        """The ``isdigit()`` guard, pinned.

        A PR key is neither a digit nor an existing path from this cwd, so it
        is refused with the message that names both accepted forms — rather
        than being globbed for and silently missing.
        """
        with pytest.raises(MetrologyTargetError):
            resolve_target("github.com/ecorkran/squadron#42", None, str(both_reviews))


class TestTargetKindClassifies:
    """The ``*-review.*`` family reads frontmatter, never the filename (D4)."""

    def test_both_artifacts_declare_what_they_are(self, both_reviews: Path, pr_name: str) -> None:
        reviews = both_reviews / REVIEWS_DIR
        slice_fm = read_review_frontmatter(reviews / _SLICE_NAME)
        pr_fm = read_review_frontmatter(reviews / pr_name)

        assert slice_fm["targetKind"] == "slice"
        assert pr_fm["targetKind"] == "pr"

    def test_absence_of_target_kind_means_slice(self, tmp_path: Path) -> None:
        """Every artifact written before 383 keeps parsing (D4).

        The key is additive and optional. A consumer that treated its absence
        as unknown would strand every review in every existing project.
        """
        reviews = tmp_path / REVIEWS_DIR
        reviews.mkdir(parents=True)
        legacy = _SLICE_REVIEW.replace("targetKind: slice\n", "").replace("rulesSource: project\n", "")
        path = reviews / _SLICE_NAME
        path.write_text(legacy, encoding="utf-8")

        frontmatter = read_review_frontmatter(path)

        assert "targetKind" not in frontmatter
        assert frontmatter.get("targetKind", "slice") == "slice"
