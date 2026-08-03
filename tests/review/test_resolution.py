"""Tests for ``sq review resolve``'s review location and loading."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from squadron.review.models import Verdict
from squadron.review.persistence import REVIEWS_DIR
from squadron.review.resolution import (
    ResolutionError,
    load_review,
    locate_review,
    review_type_of,
)

_REVIEW_WITH_FINDINGS = """\
---
docType: review
reviewType: code
slice: findings-addressed
verdict: CONCERNS
reviewedSha: abc1234
findings:
  - id: F001
    severity: fail
    category: error-handling
    summary: "Unhandled OSError on write"
    location: src/foo.py:10
  - id: F002
    severity: note
    category: naming
    summary: "Variable name unclear"
    location: src/bar.py:3
---

# Review: code — slice 305
"""


def _write_review(cwd: Path, filename: str, content: str = _REVIEW_WITH_FINDINGS) -> Path:
    reviews_dir = cwd / REVIEWS_DIR
    reviews_dir.mkdir(parents=True, exist_ok=True)
    path = reviews_dir / filename
    path.write_text(content, encoding="utf-8")
    return path


class TestLocateReview:
    def test_single_review_resolves_without_a_type(self, tmp_path: Path) -> None:
        expected = _write_review(tmp_path, "305-review.code.findings-addressed.md")
        assert locate_review(305, None, str(tmp_path)) == expected
        assert review_type_of(expected) == "code"

    def test_explicit_type_selects_among_several(self, tmp_path: Path) -> None:
        _write_review(tmp_path, "305-review.code.findings-addressed.md")
        expected = _write_review(tmp_path, "305-review.tasks.findings-addressed.md")
        assert locate_review(305, "tasks", str(tmp_path)) == expected

    def test_ambiguous_index_lists_every_match(self, tmp_path: Path) -> None:
        """305's real on-disk state: a code review and a tasks review."""
        _write_review(tmp_path, "305-review.code.findings-addressed.md")
        _write_review(tmp_path, "305-review.tasks.findings-addressed.md")

        with pytest.raises(ResolutionError) as excinfo:
            locate_review(305, None, str(tmp_path))

        message = str(excinfo.value)
        assert "305-review.code.findings-addressed.md" in message
        assert "305-review.tasks.findings-addressed.md" in message

    def test_missing_explicit_type_names_the_expected_path(self, tmp_path: Path) -> None:
        _write_review(tmp_path, "305-review.code.findings-addressed.md")

        with pytest.raises(ResolutionError) as excinfo:
            locate_review(305, "arch", str(tmp_path))

        message = str(excinfo.value)
        assert "305-review.arch.*.md" in message
        assert str(tmp_path / REVIEWS_DIR) in message

    def test_no_review_for_the_index(self, tmp_path: Path) -> None:
        _write_review(tmp_path, "305-review.code.findings-addressed.md")

        with pytest.raises(ResolutionError, match="306-review"):
            locate_review(306, None, str(tmp_path))


class TestLoadReview:
    def test_reads_verdict_sha_and_findings(self, tmp_path: Path) -> None:
        path = _write_review(tmp_path, "305-review.code.findings-addressed.md")
        loaded = load_review(path)

        assert loaded.verdict == Verdict.CONCERNS
        assert loaded.frontmatter["reviewedSha"] == "abc1234"
        assert [record.finding_id for record in loaded.findings] == ["F001", "F002"]
        assert loaded.findings[0].severity == "FAIL"
        assert loaded.findings[0].location == "src/foo.py:10"

    def test_review_without_findings_block(self, tmp_path: Path) -> None:
        path = _write_review(
            tmp_path,
            "305-review.code.findings-addressed.md",
            "---\ndocType: review\nverdict: PASS\n---\n\n# Review\n",
        )
        loaded = load_review(path)

        assert loaded.verdict == Verdict.PASS
        assert loaded.findings == []

    def test_missing_verdict_warns_and_reads_unknown(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        path = _write_review(
            tmp_path,
            "305-review.code.findings-addressed.md",
            "---\ndocType: review\n---\n\n# Review\n",
        )
        with caplog.at_level(logging.WARNING):
            loaded = load_review(path)

        assert loaded.verdict == Verdict.UNKNOWN
        assert "verdict" in caplog.text

    def test_no_frontmatter_is_an_error_not_an_empty_result(self, tmp_path: Path) -> None:
        path = _write_review(
            tmp_path,
            "305-review.code.findings-addressed.md",
            "# Review with no frontmatter at all\n",
        )
        with pytest.raises(ResolutionError, match="frontmatter"):
            load_review(path)
