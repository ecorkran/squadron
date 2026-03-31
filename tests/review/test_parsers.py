"""Tests for review result parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.review.models import Severity, Verdict
from squadron.review.parsers import parse_review_output

WELL_FORMED_PASS = """\
## Summary
PASS

## Findings

### [PASS] Clean module structure
Package layout follows project conventions and separation of concerns.

### [PASS] Good test coverage
All critical paths have unit tests.
"""

WELL_FORMED_CONCERNS = """\
## Summary
CONCERNS

## Findings

### [CONCERN] Missing error handling
The runner does not handle SDK timeout errors gracefully.

### [PASS] Clean module structure
Package layout follows project conventions.

### [FAIL] Security issue
User input is not sanitized at the API boundary.
File: src/api/handler.py:42
"""

WELL_FORMED_FAIL = """\
## Summary
FAIL

## Findings

### [FAIL] Critical bug in auth
Token validation is bypassed when header is empty.

### [FAIL] SQL injection risk
Query parameters are interpolated directly.
"""


class TestVerdictExtraction:
    """Test verdict parsing across all verdict strings."""

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("## Summary\nPASS\n", Verdict.PASS),
            ("## Summary\nCONCERNS\n", Verdict.CONCERNS),
            ("## Summary\nFAIL\n", Verdict.FAIL),
            ("## Summary\n\nPASS\n", Verdict.PASS),
            ("##  Summary \nFAIL\n", Verdict.FAIL),
            ("## Summary\n**PASS**\n", Verdict.PASS),
            ("## Summary\n**CONCERNS**\n", Verdict.CONCERNS),
            ("## Summary\n**FAIL**\n", Verdict.FAIL),
        ],
    )
    def test_verdict_values(self, text: str, expected: Verdict) -> None:
        result = parse_review_output(text, "test", {})
        assert result.verdict == expected


class TestWellFormedOutput:
    """Test parsing well-formed agent output."""

    def test_pass_verdict_with_findings(self) -> None:
        result = parse_review_output(WELL_FORMED_PASS, "arch", {"input": "a.md"})
        assert result.verdict == Verdict.PASS
        assert len(result.findings) == 2
        assert all(f.severity == Severity.PASS for f in result.findings)

    def test_concerns_verdict_mixed_findings(self) -> None:
        result = parse_review_output(WELL_FORMED_CONCERNS, "code", {"cwd": "."})
        assert result.verdict == Verdict.CONCERNS
        assert len(result.findings) == 3
        severities = [f.severity for f in result.findings]
        assert Severity.CONCERN in severities
        assert Severity.PASS in severities
        assert Severity.FAIL in severities

    def test_fail_verdict(self) -> None:
        result = parse_review_output(WELL_FORMED_FAIL, "code", {})
        assert result.verdict == Verdict.FAIL
        assert len(result.findings) == 2
        assert all(f.severity == Severity.FAIL for f in result.findings)

    def test_finding_titles(self) -> None:
        result = parse_review_output(WELL_FORMED_CONCERNS, "code", {})
        titles = [f.title for f in result.findings]
        assert "Missing error handling" in titles
        assert "Security issue" in titles

    def test_finding_descriptions(self) -> None:
        result = parse_review_output(WELL_FORMED_CONCERNS, "code", {})
        concern = next(f for f in result.findings if f.severity == Severity.CONCERN)
        assert "timeout" in concern.description.lower()


class TestBracketOptionalFindings:
    """Test parsing findings without brackets (real agent output format)."""

    def test_no_brackets(self) -> None:
        text = """\
## Summary
**PASS**

## Findings

### PASS Good structure
Clean layout.

### CONCERN Missing tests
No tests for edge cases.

### FAIL Security hole
SQL injection possible.
"""
        result = parse_review_output(text, "code", {})
        assert result.verdict == Verdict.PASS
        assert len(result.findings) == 3
        severities = [f.severity for f in result.findings]
        assert Severity.PASS in severities
        assert Severity.CONCERN in severities
        assert Severity.FAIL in severities

    def test_mixed_brackets_and_no_brackets(self) -> None:
        text = """\
## Summary
CONCERNS

## Findings

### [PASS] With brackets
Description.

### CONCERN Without brackets
Description.
"""
        result = parse_review_output(text, "arch", {})
        assert len(result.findings) == 2


class TestMalformedOutput:
    """Test parsing malformed agent output."""

    def test_missing_summary(self) -> None:
        result = parse_review_output("Some text without a summary section.", "arch", {})
        assert result.verdict == Verdict.UNKNOWN

    def test_empty_output(self) -> None:
        result = parse_review_output("", "arch", {})
        assert result.verdict == Verdict.UNKNOWN
        assert result.findings == []

    def test_partial_output_findings_only_bracketed(self) -> None:
        text = "### [FAIL] Something wrong\nDescription here.\n"
        result = parse_review_output(text, "code", {})
        assert result.verdict == Verdict.UNKNOWN
        assert len(result.findings) == 1
        assert result.findings[0].severity == Severity.FAIL

    def test_partial_output_findings_only_unbracketed(self) -> None:
        text = "### FAIL Something wrong\nDescription here.\n"
        result = parse_review_output(text, "code", {})
        assert result.verdict == Verdict.UNKNOWN
        assert len(result.findings) == 1
        assert result.findings[0].severity == Severity.FAIL

    def test_summary_without_findings(self) -> None:
        text = "## Summary\nPASS\n\nNo specific findings.\n"
        result = parse_review_output(text, "arch", {})
        assert result.verdict == Verdict.PASS
        assert result.findings == []


class TestUnknownFallback:
    """Test UNKNOWN fallback preserves raw output."""

    def test_raw_output_preserved(self) -> None:
        raw = "This is completely unstructured agent output."
        result = parse_review_output(raw, "tasks", {"input": "x"})
        assert result.verdict == Verdict.UNKNOWN
        assert result.raw_output == raw
        assert result.template_name == "tasks"
        assert result.input_files == {"input": "x"}

    def test_metadata_preserved_on_success(self) -> None:
        result = parse_review_output(
            WELL_FORMED_PASS, "arch", {"input": "a.md", "against": "b.md"}
        )
        assert result.template_name == "arch"
        assert result.input_files == {"input": "a.md", "against": "b.md"}
        assert result.raw_output == WELL_FORMED_PASS


# ---------------------------------------------------------------------------
# T2: Expanded _FINDING_RE format variants
# ---------------------------------------------------------------------------


class TestExpandedFindingFormats:
    """Test the five finding format variants supported by _FINDING_RE."""

    def test_finding_colon_separator(self) -> None:
        """### CONCERN: My title parses to CONCERN finding."""
        text = "## Summary\nCONCERNS\n\n### CONCERN: My title\nSome detail.\n"
        result = parse_review_output(text, "slice", {})
        assert len(result.findings) == 1
        assert result.findings[0].severity == Severity.CONCERN
        assert result.findings[0].title == "My title"

    def test_finding_bold_brackets(self) -> None:
        """**[FAIL]** My title parses to FAIL finding."""
        text = "## Summary\nFAIL\n\n**[FAIL]** My title\nSome detail.\n"
        result = parse_review_output(text, "code", {})
        assert len(result.findings) == 1
        assert result.findings[0].severity == Severity.FAIL
        assert result.findings[0].title == "My title"

    def test_finding_bullet_point(self) -> None:
        """- [CONCERN] My title parses to CONCERN finding."""
        text = "## Summary\nCONCERNS\n\n- [CONCERN] My title\nSome detail.\n"
        result = parse_review_output(text, "tasks", {})
        assert len(result.findings) == 1
        assert result.findings[0].severity == Severity.CONCERN
        assert result.findings[0].title == "My title"

    def test_finding_standard_brackets(self) -> None:
        """### [CONCERN] Title — existing format still parses correctly."""
        text = "## Summary\nCONCERNS\n\n### [CONCERN] Standard brackets\nDetail.\n"
        result = parse_review_output(text, "slice", {})
        assert len(result.findings) == 1
        assert result.findings[0].severity == Severity.CONCERN

    def test_finding_standard_no_brackets(self) -> None:
        """### CONCERN Title — existing no-brackets format still parses correctly."""
        text = "## Summary\nCONCERNS\n\n### CONCERN No brackets\nDetail.\n"
        result = parse_review_output(text, "slice", {})
        assert len(result.findings) == 1
        assert result.findings[0].severity == Severity.CONCERN


# ---------------------------------------------------------------------------
# T4: Fallback parsing
# ---------------------------------------------------------------------------


class TestFallbackParsing:
    """Test fallback parsing for verdict/findings mismatches."""

    def test_fallback_synthesizes_finding(self) -> None:
        """CONCERNS verdict + no parseable findings → single synthesized finding."""
        text = (
            "## Summary\nCONCERNS\n\nThis review has some issues but unclear format.\n"
        )
        result = parse_review_output(text, "slice", {})
        assert result.verdict == Verdict.CONCERNS
        assert len(result.findings) == 1
        assert result.findings[0].title == "Unparsed review findings"
        assert result.findings[0].severity == Severity.CONCERN

    def test_fallback_not_triggered_on_pass(self) -> None:
        """PASS with no findings → no fallback, findings list stays empty."""
        text = "## Summary\nPASS\n\nLooks good overall.\n"
        result = parse_review_output(text, "slice", {})
        assert result.verdict == Verdict.PASS
        assert result.findings == []
        assert result.fallback_used is False

    def test_fallback_used_flag_true_when_triggered(self) -> None:
        """result.fallback_used is True when fallback triggered."""
        text = "## Summary\nFAIL\n\nCritical issues found.\n"
        result = parse_review_output(text, "code", {})
        assert result.fallback_used is True

    def test_fallback_used_flag_false_on_clean_parse(self) -> None:
        """result.fallback_used is False when standard parsing succeeds."""
        text = "## Summary\nCONCERNS\n\n### [CONCERN] Missing tests\nNo tests.\n"
        result = parse_review_output(text, "slice", {})
        assert result.fallback_used is False

    def test_lenient_finds_paragraph_findings(self) -> None:
        """CONCERNS verdict with findings in paragraph format → lenient path."""
        text = (
            "## Summary\nCONCERNS\n\n"
            "CONCERN: Input validation is missing\n"
            "The handler does not validate user input.\n"
        )
        result = parse_review_output(text, "slice", {})
        assert result.verdict == Verdict.CONCERNS
        assert len(result.findings) >= 1
        assert result.fallback_used is True


# ---------------------------------------------------------------------------
# T6: Diagnostic logging
# ---------------------------------------------------------------------------


class TestDiagnosticLogging:
    """Test debug log written on verdict/findings mismatches."""

    def test_debug_log_written_on_mismatch(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CONCERNS + empty findings → log file written."""
        log_file = tmp_path / "review-debug.jsonl"
        monkeypatch.setattr("squadron.review.parsers._DEBUG_LOG_PATH", log_file)
        text = "## Summary\nCONCERNS\n\nSome unstructured content.\n"
        parse_review_output(text, "slice", {}, model="minimax")
        assert log_file.exists()
        import json

        entries = [json.loads(line) for line in log_file.read_text().splitlines()]
        assert len(entries) >= 1
        assert entries[0]["verdict"] == "CONCERNS"
        assert entries[0]["template"] == "slice"
        assert entries[0]["model"] == "minimax"

    def test_debug_log_not_written_on_clean_pass(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """PASS with findings → no log write."""
        log_file = tmp_path / "review-debug.jsonl"
        monkeypatch.setattr("squadron.review.parsers._DEBUG_LOG_PATH", log_file)
        text = "## Summary\nPASS\n\n### [PASS] Clean code\nLooks good.\n"
        parse_review_output(text, "code", {})
        assert not log_file.exists()


# ---------------------------------------------------------------------------
# T6: ReviewResult prompt capture fields
# ---------------------------------------------------------------------------

from squadron.review.models import ReviewResult  # noqa: E402


class TestReviewResultPromptFields:
    """Tests for prompt capture fields on ReviewResult."""

    def test_prompt_fields_default_none(self) -> None:
        result = ReviewResult(
            verdict=Verdict.PASS,
            findings=[],
            raw_output="ok",
            template_name="test",
            input_files={},
        )
        assert result.system_prompt is None
        assert result.user_prompt is None
        assert result.rules_content_used is None

    def test_prompt_fields_populated(self) -> None:
        result = ReviewResult(
            verdict=Verdict.PASS,
            findings=[],
            raw_output="ok",
            template_name="test",
            input_files={},
            system_prompt="sys",
            user_prompt="usr",
            rules_content_used="rules",
        )
        assert result.system_prompt == "sys"
        assert result.user_prompt == "usr"
        assert result.rules_content_used == "rules"

    def test_to_dict_excludes_prompt_fields(self) -> None:
        result = ReviewResult(
            verdict=Verdict.PASS,
            findings=[],
            raw_output="ok",
            template_name="test",
            input_files={},
            system_prompt="sys",
            user_prompt="usr",
            rules_content_used="rules",
        )
        d = result.to_dict()
        assert "system_prompt" not in d
        assert "user_prompt" not in d
        assert "rules_content_used" not in d


# ---------------------------------------------------------------------------
# T4: NOTE severity and category/location extraction
# ---------------------------------------------------------------------------


class TestNoteSeverityParsing:
    """Test NOTE severity parsed from all finding formats."""

    def test_note_bracketed_heading(self) -> None:
        text = "## Summary\nPASS\n\n### [NOTE] Informational\nJust a note.\n"
        result = parse_review_output(text, "code", {})
        assert len(result.findings) == 1
        assert result.findings[0].severity == Severity.NOTE

    def test_note_unbracketed_heading(self) -> None:
        text = "## Summary\nPASS\n\n### NOTE Informational\nJust a note.\n"
        result = parse_review_output(text, "code", {})
        assert len(result.findings) == 1
        assert result.findings[0].severity == Severity.NOTE

    def test_note_bold_brackets(self) -> None:
        text = "## Summary\nPASS\n\n**[NOTE]** Informational\nJust a note.\n"
        result = parse_review_output(text, "code", {})
        assert len(result.findings) == 1
        assert result.findings[0].severity == Severity.NOTE

    def test_note_bullet(self) -> None:
        text = "## Summary\nPASS\n\n- [NOTE] Informational\nJust a note.\n"
        result = parse_review_output(text, "code", {})
        assert len(result.findings) == 1
        assert result.findings[0].severity == Severity.NOTE


class TestCategoryExtraction:
    """Test category: tag extraction from finding bodies."""

    def test_category_extracted(self) -> None:
        text = (
            "## Summary\nCONCERNS\n\n"
            "### [CONCERN] Missing error handling\n"
            "category: error-handling\n"
            "No try/except around file read.\n"
        )
        result = parse_review_output(text, "code", {})
        assert result.findings[0].category == "error-handling"

    def test_category_different_value(self) -> None:
        text = (
            "## Summary\nCONCERNS\n\n"
            "### [CONCERN] Unclear naming\n"
            "category: naming\n"
            "Variable x is unclear.\n"
        )
        result = parse_review_output(text, "code", {})
        assert result.findings[0].category == "naming"

    def test_no_category_returns_none(self) -> None:
        text = "## Summary\nCONCERNS\n\n### [CONCERN] Something\nJust description.\n"
        result = parse_review_output(text, "code", {})
        assert result.findings[0].category is None

    def test_category_stripped_from_description(self) -> None:
        text = (
            "## Summary\nCONCERNS\n\n"
            "### [CONCERN] Missing validation\n"
            "category: validation\n"
            "Input not checked.\n"
        )
        result = parse_review_output(text, "code", {})
        assert "category:" not in result.findings[0].description
        assert "Input not checked" in result.findings[0].description

    def test_category_case_insensitive(self) -> None:
        text = (
            "## Summary\nCONCERNS\n\n"
            "### [CONCERN] Title\n"
            "Category: error-handling\n"
            "Detail.\n"
        )
        result = parse_review_output(text, "code", {})
        assert result.findings[0].category == "error-handling"

    def test_category_uppercase(self) -> None:
        text = (
            "## Summary\nCONCERNS\n\n### [CONCERN] Title\nCATEGORY: naming\nDetail.\n"
        )
        result = parse_review_output(text, "code", {})
        assert result.findings[0].category == "naming"


class TestLocationExtraction:
    """Test location: tag extraction from finding bodies."""

    def test_location_extracted(self) -> None:
        text = (
            "## Summary\nCONCERNS\n\n"
            "### [CONCERN] Bug\n"
            "location: src/foo.py:45\n"
            "Some detail.\n"
        )
        result = parse_review_output(text, "code", {})
        assert result.findings[0].location == "src/foo.py:45"

    def test_location_stripped_from_description(self) -> None:
        text = (
            "## Summary\nCONCERNS\n\n"
            "### [CONCERN] Bug\n"
            "location: src/foo.py:45\n"
            "Some detail.\n"
        )
        result = parse_review_output(text, "code", {})
        assert "location:" not in result.findings[0].description

    def test_no_location_returns_none(self) -> None:
        text = "## Summary\nCONCERNS\n\n### [CONCERN] Bug\nSome detail.\n"
        result = parse_review_output(text, "code", {})
        assert result.findings[0].location is None

    def test_both_category_and_location(self) -> None:
        text = (
            "## Summary\nCONCERNS\n\n"
            "### [CONCERN] Bug\n"
            "category: error-handling\n"
            "location: src/foo.py:45\n"
            "Detail here.\n"
        )
        result = parse_review_output(text, "code", {})
        f = result.findings[0]
        assert f.category == "error-handling"
        assert f.location == "src/foo.py:45"

    def test_file_ref_populates_location(self) -> None:
        """-> path/to/file.py:123 also populates location when no location: tag."""
        text = (
            "## Summary\nCONCERNS\n\n"
            "### [CONCERN] Bug\n"
            "Some detail.\n"
            "-> src/handler.py:42\n"
        )
        result = parse_review_output(text, "code", {})
        f = result.findings[0]
        assert f.file_ref == "src/handler.py:42"
        assert f.location == "src/handler.py:42"


class TestExistingFormatsRegression:
    """Ensure existing PASS, CONCERN, FAIL formats still work after NOTE addition."""

    @pytest.mark.parametrize(
        ("sev_str", "expected"),
        [
            ("PASS", Severity.PASS),
            ("CONCERN", Severity.CONCERN),
            ("FAIL", Severity.FAIL),
        ],
    )
    def test_bracketed_heading(self, sev_str: str, expected: Severity) -> None:
        text = f"## Summary\nPASS\n\n### [{sev_str}] Title\nDetail.\n"
        result = parse_review_output(text, "code", {})
        assert len(result.findings) == 1
        assert result.findings[0].severity == expected
