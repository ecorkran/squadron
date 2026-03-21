"""Tests for review result models."""

from __future__ import annotations

import json

import pytest

from squadron.review.models import (
    ReviewFinding,
    ReviewResult,
    Severity,
    Verdict,
)


class TestVerdict:
    """Verdict enum string values."""

    @pytest.mark.parametrize(
        ("member", "expected"),
        [
            (Verdict.PASS, "PASS"),
            (Verdict.CONCERNS, "CONCERNS"),
            (Verdict.FAIL, "FAIL"),
            (Verdict.UNKNOWN, "UNKNOWN"),
        ],
    )
    def test_string_values(self, member: Verdict, expected: str) -> None:
        assert member.value == expected
        assert str(member) == expected


class TestSeverity:
    """Severity enum string values."""

    @pytest.mark.parametrize(
        ("member", "expected"),
        [
            (Severity.PASS, "PASS"),
            (Severity.CONCERN, "CONCERN"),
            (Severity.FAIL, "FAIL"),
        ],
    )
    def test_string_values(self, member: Severity, expected: str) -> None:
        assert member.value == expected
        assert str(member) == expected


class TestReviewFinding:
    """ReviewFinding dataclass."""

    def test_with_file_ref(self) -> None:
        finding = ReviewFinding(
            severity=Severity.FAIL,
            title="Missing validation",
            description="Input not validated at boundary.",
            file_ref="src/app.py:10",
        )
        assert finding.severity == Severity.FAIL
        assert finding.title == "Missing validation"
        assert finding.file_ref == "src/app.py:10"

    def test_without_file_ref(self) -> None:
        finding = ReviewFinding(
            severity=Severity.PASS,
            title="Good structure",
            description="Module layout is clean.",
        )
        assert finding.file_ref is None


class TestReviewResult:
    """ReviewResult dataclass construction, serialization, and properties."""

    @pytest.fixture
    def result_with_mixed_findings(self) -> ReviewResult:
        return ReviewResult(
            verdict=Verdict.CONCERNS,
            findings=[
                ReviewFinding(
                    severity=Severity.FAIL,
                    title="Critical bug",
                    description="Null pointer.",
                ),
                ReviewFinding(
                    severity=Severity.CONCERN,
                    title="Naming",
                    description="Inconsistent names.",
                ),
                ReviewFinding(
                    severity=Severity.CONCERN,
                    title="Style",
                    description="Line too long.",
                ),
                ReviewFinding(
                    severity=Severity.PASS,
                    title="Tests present",
                    description="Good coverage.",
                ),
            ],
            raw_output="raw text here",
            template_name="code",
            input_files={"cwd": ".", "files": "src/**/*.py"},
        )

    def test_construction(self, result_with_mixed_findings: ReviewResult) -> None:
        r = result_with_mixed_findings
        assert r.verdict == Verdict.CONCERNS
        assert len(r.findings) == 4
        assert r.template_name == "code"
        assert r.timestamp is not None

    def test_has_failures_true(self, result_with_mixed_findings: ReviewResult) -> None:
        assert result_with_mixed_findings.has_failures is True

    def test_has_failures_false(self) -> None:
        r = ReviewResult(
            verdict=Verdict.PASS,
            findings=[
                ReviewFinding(
                    severity=Severity.PASS,
                    title="OK",
                    description="Fine.",
                ),
            ],
            raw_output="",
            template_name="arch",
            input_files={"input": "a.md"},
        )
        assert r.has_failures is False

    def test_concern_count(self, result_with_mixed_findings: ReviewResult) -> None:
        assert result_with_mixed_findings.concern_count == 2

    def test_to_dict_serializable(
        self, result_with_mixed_findings: ReviewResult
    ) -> None:
        d = result_with_mixed_findings.to_dict()
        # Must be JSON-serializable
        serialized = json.dumps(d)
        assert isinstance(serialized, str)

    def test_to_dict_structure(self, result_with_mixed_findings: ReviewResult) -> None:
        d = result_with_mixed_findings.to_dict()
        assert d["verdict"] == "CONCERNS"
        assert d["template_name"] == "code"
        assert "raw_output" not in d
        assert len(d["findings"]) == 4
        assert d["findings"][0]["severity"] == "FAIL"
        assert d["findings"][0]["title"] == "Critical bug"
        assert d["findings"][0]["file_ref"] is None
        assert "timestamp" in d
        assert isinstance(d["input_files"], dict)

    def test_empty_findings(self) -> None:
        r = ReviewResult(
            verdict=Verdict.PASS,
            findings=[],
            raw_output="",
            template_name="arch",
            input_files={},
        )
        assert r.has_failures is False
        assert r.concern_count == 0
        assert r.to_dict()["findings"] == []
