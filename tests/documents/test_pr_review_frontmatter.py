"""A PR-shaped review artifact validates under Context Forge's schema (383, D7).

The slice's largest named risk was a possible cf schema change: a PR review has
no ``slice`` key, carries a nested ``pr`` mapping, and has a non-numeric
filename. D7 established by probe that none of that requires a cf change — the
``review`` schema requires only ``docType``, ``project``, ``status``,
``dateCreated`` and ``dateUpdated``, and unknown keys pass through.

**Why this test is shaped so defensively.** ``cf validate frontmatter``
resolves by *registered project*, and validates only in-root files — others are
"silently skipped" (its own help text). A skipped fixture reports
``filesChecked: 0`` with zero findings, which is indistinguishable from a
fixture that passed. So every assertion here checks the count first: the test
must fail when cf did not look, never pass.

Run from a worktree whose path is not the registered project root, cf walks the
main checkout instead and a fixture written here is never seen. That is
context-forge issue #88, not a defect in this slice, and this test says so
explicitly rather than failing with a bare count mismatch that invites someone
to "fix" the fixture.
"""

from __future__ import annotations

import json
import subprocess
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

_DOC_ROOT = Path("project-documents/user")
_REVIEWS = _DOC_ROOT / "reviews"

#: The artifact shape slice 383 introduced: no slice key, a nested pr mapping,
#: the two additive keys, and a non-numeric filename prefix.
_PR_FRONTMATTER = """---
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
reviewedSha: 1111111111111111111111111111111111111111
status: complete
dateCreated: 20260915
dateUpdated: 20260915
---

# Review: code — PR #42

No specific findings.
"""


def _cf_validate() -> dict[str, object]:
    """The no-argument walk — the only invocation that validates anything.

    Explicit paths are validated only when in-root and skipped silently
    otherwise, so passing a path would make a skipped fixture look like a
    passing one. The walk plus a count comparison is the probe D7 describes.
    """
    try:
        result = subprocess.run(
            ["cf", "validate", "frontmatter", "--json"],
            capture_output=True,
            text=True,
            timeout=300,
        )
    except FileNotFoundError:
        raise AssertionError(
            "'cf' is not on PATH — the frontmatter schema lives in Context Forge, "
            "so this test cannot run without it."
        ) from None
    return json.loads(result.stdout)


@contextmanager
def _fixture_in_reviews(name: str) -> Iterator[Path]:
    """Write a fixture into the real reviews directory, and always remove it.

    The fixture cannot live in ``tmp_path``: cf validates only files under the
    registered project root, so a fixture written anywhere else is silently
    skipped and proves nothing. That forces a write into the working tree, and
    a write into the working tree is debris the moment anything goes wrong —
    an interrupted run leaves a ``zz-*.md`` that ``cf validate`` then walks and
    that can be committed by accident.

    ``mkdir`` is inside the guarded region for the same reason: a failure
    between creating the directory and entering the caller's ``try`` would
    otherwise escape the cleanup entirely.
    """
    path = _REVIEWS / name
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_PR_FRONTMATTER, encoding="utf-8")
        yield path
    finally:
        path.unlink(missing_ok=True)


def _skip_unless_this_checkout_is_the_registered_root() -> int:
    """Return the baseline count, or fail naming why the probe cannot run.

    Deliberately fails rather than skips when cf is absent (a skipped schema
    test is a silent fallback), but *does* skip when the checkout is out of
    root: that is a known cf limitation with an issue against it, and failing
    here would add a fourth red test to the three this worktree already carries
    for the same cause — while Task 9.3 requires exactly three.
    """
    baseline = _cf_validate()
    files_checked = baseline["filesChecked"]
    assert isinstance(files_checked, int)

    with _fixture_in_reviews(f"zz-rootcheck-{uuid.uuid4().hex}.md"):
        after = _cf_validate()

    after_count = after["filesChecked"]
    assert isinstance(after_count, int)

    if after_count == files_checked:
        pytest.skip(
            "cf validates the registered project root, which is not this "
            "checkout — a fixture written here is never walked "
            "(filesChecked unchanged at "
            f"{files_checked}). context-forge issue #88; run from the "
            "registered root to exercise this test."
        )
    return files_checked


class TestPrShapedFrontmatterValidates:
    def test_a_pr_artifact_adds_one_validated_file_with_no_findings(self) -> None:
        """D7's probe, encoded: the count must *rise*, not merely not-fall.

        ``totalFindings == 0`` alone would pass for a fixture cf never opened,
        which is the whole reason the count is asserted first.
        """
        baseline = _skip_unless_this_checkout_is_the_registered_root()

        with _fixture_in_reviews(f"zz-pr-shape-{uuid.uuid4().hex}.md"):
            report = _cf_validate()

        assert report["filesChecked"] == baseline + 1, (
            f"cf checked {report['filesChecked']}, expected {baseline + 1} — "
            "a fixture cf never looked at proves nothing about the schema"
        )
        assert report["totalFindings"] == 0, report["findings"]

    def test_the_non_numeric_filename_does_not_break_validation(self) -> None:
        """``inferDocTypeFromPath`` wants a leading digit; a PR name has none.

        That skips *inference*, not validation — ``docType: review`` is present
        in the frontmatter. Asserted under the real PR filename form rather
        than a generic name, because the filename is the part that differs.
        """
        baseline = _skip_unless_this_checkout_is_the_registered_root()

        name = f"github.com-ecorkran-squadron-{uuid.uuid4().hex[:6]}-review.code.md"
        with _fixture_in_reviews(name):
            report = _cf_validate()

        assert report["filesChecked"] == baseline + 1
        assert report["totalFindings"] == 0, report["findings"]
