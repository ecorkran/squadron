"""Tests for the review-file findings reader in ``review/addressed/models``."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import cast

import pytest
import yaml

from squadron.review.addressed.models import (
    FindingRecord,
    concern_plus,
    records_from_frontmatter,
)
from squadron.review.models import ReviewFinding, ReviewResult, Severity, Verdict
from squadron.review.persistence import SliceInfo, format_review_markdown


def _slice_info() -> SliceInfo:
    return SliceInfo(
        index=305,
        name="findings-addressed",
        slice_name="findings-addressed",
        design_file="project-documents/user/slices/305-slice.findings-addressed.md",
        task_files=["305-tasks.findings-addressed.md"],
        arch_file="project-documents/user/architecture/300-arch.md",
        project="squadron",
    )


def _rendered_findings(findings: list[ReviewFinding]) -> list[object]:
    """Render *findings* through the real writer and read the block back out.

    The point of routing through ``format_review_markdown`` rather than a
    hand-built dict list is 305's F002 lesson: this parser must be exercised
    against the shape its actual producer emits.
    """
    result = ReviewResult(
        verdict=Verdict.CONCERNS,
        findings=findings,
        raw_output="raw review output",
        template_name="code",
        input_files={"input": "file.md"},
        timestamp=datetime(2026, 8, 3, 12, 0, 0),
        model="claude-opus-4-5",
    )
    markdown = format_review_markdown(result, "code", _slice_info(), reviewed_sha="deadbeef")
    frontmatter = markdown.split("---", 2)[1]
    parsed = cast(dict[str, object], yaml.safe_load(frontmatter))
    return cast(list[object], parsed["findings"])


class TestRecordsFromFrontmatter:
    def test_round_trips_a_real_rendered_review(self) -> None:
        """CONCERN+ findings survive render → parse → read with fields intact."""
        raw_findings = _rendered_findings(
            [
                ReviewFinding(
                    severity=Severity.FAIL,
                    title="Unhandled OSError on write",
                    description="save() never guards the write.",
                    category="error-handling",
                    location="src/foo.py:10",
                ),
                ReviewFinding(
                    severity=Severity.CONCERN,
                    title="Duplicated normalization",
                    description="Two readers normalize severity differently.",
                    category="duplication",
                    location="src/bar.py:42",
                ),
                ReviewFinding(
                    severity=Severity.NOTE,
                    title="Variable name unclear",
                    description="Variable x is vague.",
                    category="naming",
                    location="src/baz.py:7",
                ),
            ]
        )

        records = records_from_frontmatter(raw_findings)
        assert len(records) == 3
        assert not any(record.malformed for record in records)

        accountable = concern_plus(records)
        assert [record.finding_id for record in accountable] == ["F001", "F002"]
        # Severity is normalized to the ``Severity`` enum's case even though the
        # frontmatter shape is already lowercase — one normalization path.
        assert [record.severity for record in accountable] == [Severity.FAIL, Severity.CONCERN]
        assert accountable[0] == FindingRecord(
            finding_id="F001",
            severity=Severity.FAIL,
            category="error-handling",
            location="src/foo.py:10",
            summary="Unhandled OSError on write",
        )
        assert accountable[1].location == "src/bar.py:42"
        assert accountable[1].category == "duplication"

    def test_finding_without_location_is_malformed_and_kept(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """``location:`` is omitted entirely when a finding carries none.

        The record is residue, not a drop: a silently discarded finding is a
        silently passed resolution.
        """
        raw_findings = _rendered_findings(
            [
                ReviewFinding(
                    severity=Severity.CONCERN,
                    title="No file reference",
                    description="Reviewer named no location.",
                    category="design",
                ),
            ]
        )
        assert "location" not in cast(dict[str, object], raw_findings[0])

        with caplog.at_level(logging.WARNING):
            records = records_from_frontmatter(raw_findings)

        assert len(records) == 1
        assert records[0].malformed is True
        assert records[0].finding_id == "F001"
        assert concern_plus(records) == records
        assert "location" in caplog.text

    def test_non_mapping_entry_is_residue(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.WARNING):
            records = records_from_frontmatter(["not a mapping"])

        assert len(records) == 1
        assert records[0].malformed is True
        assert concern_plus(records) == records
