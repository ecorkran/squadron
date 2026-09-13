"""Tests for review result parser."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

import pytest

from squadron.review.models import Severity, Verdict
from squadron.review.parsers import (
    UNVERIFIED_LOCATION,
    location_line,
    location_path,
    parse_review_output,
)

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
        """A lost summary is recovered from the findings, never left UNKNOWN (#28)."""
        text = "### [FAIL] Something wrong\nDescription here.\n"
        result = parse_review_output(text, "code", {})
        assert result.verdict == Verdict.FAIL
        assert len(result.findings) == 1
        assert result.findings[0].severity == Severity.FAIL

    def test_partial_output_findings_only_unbracketed(self) -> None:
        text = "### FAIL Something wrong\nDescription here.\n"
        result = parse_review_output(text, "code", {})
        assert result.verdict == Verdict.FAIL
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
        result = parse_review_output(WELL_FORMED_PASS, "arch", {"input": "a.md", "against": "b.md"})
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
    """Test mismatch handling when a verdict has zero structured findings.

    Issue #20: earlier versions fabricated findings from unstructured prose
    (lenient keyword matching, then a synthesized single finding) when a
    model didn't follow the required ``### [SEVERITY] Title`` format. A
    fabricated finding that looks structurally valid but carries no real
    information is worse than an empty list, so the parser now leaves
    findings empty and only logs a WARNING; the raw model output remains on
    ``ReviewResult.raw_output``.
    """

    def test_mismatch_leaves_findings_empty(self) -> None:
        """CONCERNS verdict + no parseable findings → empty findings list."""
        text = "## Summary\nCONCERNS\n\nThis review has some issues but unclear format.\n"
        result = parse_review_output(text, "slice", {})
        assert result.verdict == Verdict.CONCERNS
        assert result.findings == []

    def test_mismatch_preserves_raw_output(self) -> None:
        """Raw model text is never discarded, even when findings are empty."""
        text = "## Summary\nCONCERNS\n\nThis review has some issues but unclear format.\n"
        result = parse_review_output(text, "slice", {})
        assert result.raw_output == text

    def test_fallback_not_triggered_on_pass(self) -> None:
        """PASS with no findings → no mismatch, findings list stays empty."""
        text = "## Summary\nPASS\n\nLooks good overall.\n"
        result = parse_review_output(text, "slice", {})
        assert result.verdict == Verdict.PASS
        assert result.findings == []
        assert result.fallback_used is False

    def test_fallback_used_flag_true_when_triggered(self) -> None:
        """result.fallback_used is True when a verdict/findings mismatch is detected."""
        text = "## Summary\nFAIL\n\nCritical issues found.\n"
        result = parse_review_output(text, "code", {})
        assert result.fallback_used is True
        assert result.findings == []

    def test_fallback_used_flag_false_on_clean_parse(self) -> None:
        """result.fallback_used is False when standard parsing succeeds."""
        text = "## Summary\nCONCERNS\n\n### [CONCERN] Missing tests\nNo tests.\n"
        result = parse_review_output(text, "slice", {})
        assert result.fallback_used is False

    def test_mismatch_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """A verdict/findings mismatch logs a WARNING naming the template and verdict."""
        text = "## Summary\nCONCERNS\n\nCONCERN: Input validation is missing\n"
        with caplog.at_level("WARNING"):
            result = parse_review_output(text, "slice", {})
        assert result.findings == []
        assert any("slice" in rec.message and "CONCERNS" in rec.message for rec in caplog.records)


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

    def test_debug_log_written_on_unknown_verdict(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """UNKNOWN + no findings → log file written (#61).

        This branch kept no evidence while both its siblings did, so the one parse
        failure with nothing else to reconstruct from was the least recoverable.
        """
        log_file = tmp_path / "review-debug.jsonl"
        monkeypatch.setattr("squadron.review.parsers._DEBUG_LOG_PATH", log_file)
        raw = "The model rambled without a summary section or any findings.\n"

        parse_review_output(raw, "slice", {}, model="minimax")

        assert log_file.exists()
        import json

        entries = [json.loads(line) for line in log_file.read_text().splitlines()]
        assert len(entries) == 1
        assert entries[0]["verdict"] == "UNKNOWN"
        assert entries[0]["findings_parsed"] == 0
        # The point of the entry: the model's actual words survive the failed parse.
        assert raw.strip() in entries[0]["raw_output"]

    def test_unknown_verdict_result_does_not_claim_fallback(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Nothing was derived or fabricated, so the result's own flag stays False."""
        log_file = tmp_path / "review-debug.jsonl"
        monkeypatch.setattr("squadron.review.parsers._DEBUG_LOG_PATH", log_file)

        result = parse_review_output("no summary, no findings\n", "slice", {})

        assert result.verdict is Verdict.UNKNOWN
        assert result.fallback_used is False

    def test_debug_log_key_is_degraded_not_fallback_used(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The log field is named for what it records (#87).

        ``ReviewResult.fallback_used`` means "findings were derived from a known
        verdict". The log field meant "some degraded parse happened" — a
        different fact under the same name. It is now ``degraded``; the result
        field is a serialized public contract and is unchanged.
        """
        log_file = tmp_path / "review-debug.jsonl"
        monkeypatch.setattr("squadron.review.parsers._DEBUG_LOG_PATH", log_file)

        result = parse_review_output("no summary, no findings\n", "slice", {})

        import json

        entry = json.loads(log_file.read_text().splitlines()[-1])
        assert entry["degraded"] is True
        assert "fallback_used" not in entry
        # Same parse, different fact: nothing was derived, so the result's own
        # flag stays False and its serialized key keeps its name.
        assert result.fallback_used is False
        assert result.to_dict()["fallback_used"] is False

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
        text = "## Summary\nCONCERNS\n\n### [CONCERN] Title\nCategory: error-handling\nDetail.\n"
        result = parse_review_output(text, "code", {})
        assert result.findings[0].category == "error-handling"

    def test_category_uppercase(self) -> None:
        text = "## Summary\nCONCERNS\n\n### [CONCERN] Title\nCATEGORY: naming\nDetail.\n"
        result = parse_review_output(text, "code", {})
        assert result.findings[0].category == "naming"


class TestLocationExtraction:
    """Test location: tag extraction from finding bodies."""

    def test_location_extracted(self) -> None:
        text = "## Summary\nCONCERNS\n\n### [CONCERN] Bug\nlocation: src/foo.py:45\nSome detail.\n"
        result = parse_review_output(text, "code", {})
        assert result.findings[0].location == "src/foo.py:45"

    def test_location_stripped_from_description(self) -> None:
        text = "## Summary\nCONCERNS\n\n### [CONCERN] Bug\nlocation: src/foo.py:45\nSome detail.\n"
        result = parse_review_output(text, "code", {})
        assert "location:" not in result.findings[0].description

    def test_no_location_normalized_to_unverified(self) -> None:
        # Slice 904: missing location: tag is soft-failed to "unverified"
        # rather than left as None, so downstream tooling sees one
        # consistent sentinel.
        text = "## Summary\nCONCERNS\n\n### [CONCERN] Bug\nSome detail.\n"
        result = parse_review_output(text, "code", {})
        assert result.findings[0].location == "unverified"

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
        text = "## Summary\nCONCERNS\n\n### [CONCERN] Bug\nSome detail.\n-> src/handler.py:42\n"
        result = parse_review_output(text, "code", {})
        f = result.findings[0]
        assert f.file_ref == "src/handler.py:42"
        assert f.location == "src/handler.py:42"


class TestLocationSoftFail:
    """Slice 904: missing/placeholder location: values are normalized to
    "unverified" with a WARNING."""

    def test_missing_location_normalized_and_warned(self, caplog: pytest.LogCaptureFixture) -> None:
        text = "## Summary\nCONCERNS\n\n### [CONCERN] Title here\nSome detail.\n"
        with caplog.at_level("WARNING", logger="squadron.review.parsers"):
            result = parse_review_output(text, "code", {})
        assert result.findings[0].location == "unverified"
        # WARNING names the finding ID, title, template, and verdict.
        records = [r for r in caplog.records if r.name == "squadron.review.parsers"]
        assert len(records) == 1
        message = records[0].getMessage()
        assert "F001" in message
        assert "Title here" in message
        assert "code" in message
        assert "CONCERNS" in message
        assert "unverified" in message

    def test_cited_location_produces_no_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        # Regression: a fully-cited finding must not trigger the soft-fail warning.
        text = "## Summary\nCONCERNS\n\n### [CONCERN] Bug\nlocation: src/foo.py:45\nSome detail.\n"
        with caplog.at_level("WARNING", logger="squadron.review.parsers"):
            result = parse_review_output(text, "code", {})
        assert result.findings[0].location == "src/foo.py:45"
        assert not [r for r in caplog.records if r.name == "squadron.review.parsers"]

    def test_arch_style_doc_path_parses_unchanged(self, caplog: pytest.LogCaptureFixture) -> None:
        # Non-code safety: arch/slice/tasks reviews cite documents, not code.
        # Any non-empty, non-placeholder location must be accepted as-is.
        text = (
            "## Summary\nCONCERNS\n\n"
            "### [CONCERN] Missing failure-mode coverage\n"
            "category: completeness\n"
            "location: docs/foo.md#bar\n"
            "Detail here.\n"
        )
        with caplog.at_level("WARNING", logger="squadron.review.parsers"):
            result = parse_review_output(text, "arch", {})
        assert result.findings[0].location == "docs/foo.md#bar"
        assert not [r for r in caplog.records if r.name == "squadron.review.parsers"]

    @pytest.mark.parametrize(
        "raw",
        ["-", "global", "GLOBAL", " ", "", "n/a", "None"],
    )
    def test_placeholder_values_normalized_to_unverified(
        self, raw: str, caplog: pytest.LogCaptureFixture
    ) -> None:
        text = f"## Summary\nCONCERNS\n\n### [CONCERN] Bug\nlocation: {raw}\nSome detail.\n"
        with caplog.at_level("WARNING", logger="squadron.review.parsers"):
            result = parse_review_output(text, "code", {})
        assert result.findings[0].location == "unverified"
        assert any(
            "unverified" in r.getMessage()
            for r in caplog.records
            if r.name == "squadron.review.parsers"
        )

    def test_unverified_passed_through_without_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        # Model emitted the explicit "I don't know" token — no warning.
        text = (
            "## Summary\nPASS\n\n"
            "### [PASS] Cross-cutting check passes\n"
            "category: completeness\n"
            "location: unverified\n"
            "Cannot pin to a single document.\n"
        )
        with caplog.at_level("WARNING", logger="squadron.review.parsers"):
            result = parse_review_output(text, "arch", {})
        assert result.findings[0].location == "unverified"
        assert not [r for r in caplog.records if r.name == "squadron.review.parsers"]


class TestLocationDiffMembershipAndPathExistence:
    """Slice 904: diff-membership and path-existence WARNINGs.

    Both checks are WARNING-only — findings are never modified, only flagged.
    UNVERIFIED_LOCATION is exempt from both checks.
    """

    def test_diff_member_and_existing_passes_silently(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        # File exists in tmp_path AND is in the diff set: no warnings.
        # The file is long enough to contain the cited line — since slice 917
        # a citation past the end of its file warns, which is the point.
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "foo.py").write_text("# foo\n" * 50)
        text = "## Summary\nCONCERNS\n\n### [CONCERN] Bug\nlocation: src/foo.py:42\nDetail.\n"
        with caplog.at_level("WARNING", logger="squadron.review.parsers"):
            parse_review_output(text, "code", {}, diff_files={"src/foo.py"}, cwd=tmp_path)
        assert not [r for r in caplog.records if r.name == "squadron.review.parsers"]

    def test_nonexistent_path_warns_for_both_checks(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        # Cited path is neither in the diff nor on disk — both checks warn.
        text = "## Summary\nCONCERNS\n\n### [CONCERN] Bug\nlocation: src/nonexistent.py:42\nDetail.\n"
        with caplog.at_level("WARNING", logger="squadron.review.parsers"):
            parse_review_output(
                text,
                "code",
                {},
                diff_files={"src/squadron/foo.py"},
                cwd=tmp_path,
            )
        messages = [r.getMessage() for r in caplog.records if r.name == "squadron.review.parsers"]
        # One warning from diff-membership, one from path-existence.
        assert sum("not among the files in the diff" in m for m in messages) == 1
        assert sum("does not exist on disk" in m for m in messages) == 1

    def test_existing_file_not_in_diff_warns_membership_only(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        # File exists on disk but is NOT in the diff: T8 warns, T9 silent.
        (tmp_path / "src" / "squadron").mkdir(parents=True)
        (tmp_path / "src" / "squadron" / "bar.py").write_text("# bar\n")
        text = "## Summary\nCONCERNS\n\n### [CONCERN] Bug\nlocation: src/squadron/bar.py:10\nDetail.\n"
        with caplog.at_level("WARNING", logger="squadron.review.parsers"):
            parse_review_output(
                text,
                "code",
                {},
                diff_files={"src/squadron/foo.py"},
                cwd=tmp_path,
            )
        messages = [r.getMessage() for r in caplog.records if r.name == "squadron.review.parsers"]
        assert any("not among the files in the diff" in m for m in messages)
        assert not any("does not exist on disk" in m for m in messages)

    def test_bare_filename_in_subdirectory_does_not_warn(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        # Issue #55: models cite documents by bare filename because the review
        # prompt supplies content, not repo paths. The file lives in a document
        # subdirectory, so an exact cwd/path join misses it and every finding
        # of a clean review warned.
        (tmp_path / "tasks").mkdir()
        (tmp_path / "tasks" / "913-tasks.least-privilege.md").write_text("# tasks\n")
        text = (
            "## Summary\nPASS\n\n"
            "### [PASS] All criteria covered\n"
            "location: 913-tasks.least-privilege.md\n"
            "Detail.\n"
        )
        with caplog.at_level("WARNING", logger="squadron.review.parsers"):
            parse_review_output(text, "tasks", {}, cwd=tmp_path)
        messages = [r.getMessage() for r in caplog.records if r.name == "squadron.review.parsers"]
        assert not any("does not exist on disk" in m for m in messages)

    def test_bare_filename_that_exists_nowhere_still_warns(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        # The hallucination defense must survive the fix above: a filename that
        # is nowhere under the root still warns, or the check stops earning its
        # keep.
        (tmp_path / "tasks").mkdir()
        (tmp_path / "tasks" / "913-tasks.least-privilege.md").write_text("# tasks\n")
        text = (
            "## Summary\nCONCERNS\n\n"
            "### [CONCERN] Invented citation\n"
            "location: 913-tasks.invented-by-the-model.md\n"
            "Detail.\n"
        )
        with caplog.at_level("WARNING", logger="squadron.review.parsers"):
            parse_review_output(text, "tasks", {}, cwd=tmp_path)
        messages = [r.getMessage() for r in caplog.records if r.name == "squadron.review.parsers"]
        assert any("does not exist on disk" in m for m in messages)

    def test_arch_review_nonexistent_doc_warns_path_existence(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        # Arch reviews have no diff, so only path-existence (T9) fires.
        text = (
            "## Summary\nCONCERNS\n\n"
            "### [CONCERN] Missing coverage\n"
            "category: completeness\n"
            "location: project-documents/nonexistent.md\n"
            "Detail.\n"
        )
        with caplog.at_level("WARNING", logger="squadron.review.parsers"):
            parse_review_output(text, "arch", {}, cwd=tmp_path)
        messages = [r.getMessage() for r in caplog.records if r.name == "squadron.review.parsers"]
        assert any("does not exist on disk" in m for m in messages)

    def test_arch_review_existing_doc_passes_silently(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "arch.md").write_text("# Arch\n")
        text = (
            "## Summary\nPASS\n\n"
            "### [PASS] Layered cleanly\n"
            "category: abstraction\n"
            "location: docs/arch.md#layers\n"
            "Detail.\n"
        )
        with caplog.at_level("WARNING", logger="squadron.review.parsers"):
            parse_review_output(text, "arch", {}, cwd=tmp_path)
        assert not [r for r in caplog.records if r.name == "squadron.review.parsers"]

    def test_trailing_annotation_after_path_is_not_part_of_path(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        # Real model output sometimes appends prose after a bare filename
        # citation, e.g. "foo.py (and related)" with no ':line' suffix.
        # The trailing annotation must not be treated as part of the path,
        # or a genuinely-valid citation triggers false-positive warnings.
        (tmp_path / "tests" / "cli" / "commands").mkdir(parents=True)
        (tmp_path / "tests" / "cli" / "commands" / "test_run_pipeline_sdk.py").write_text("# t\n")
        text = (
            "## Summary\nPASS\n\n"
            "### [PASS] Load test assertions present\n"
            "location: tests/cli/commands/test_run_pipeline_sdk.py (and related)\n"
            "Detail.\n"
        )
        with caplog.at_level("WARNING", logger="squadron.review.parsers"):
            parse_review_output(
                text,
                "code",
                {},
                diff_files={"tests/cli/commands/test_run_pipeline_sdk.py"},
                cwd=tmp_path,
            )
        assert not [r for r in caplog.records if r.name == "squadron.review.parsers"]

    def test_unverified_skips_both_checks(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        # An explicitly-`unverified` location must not trigger either check.
        text = (
            "## Summary\nPASS\n\n"
            "### [PASS] Cross-cutting\n"
            "category: completeness\n"
            "location: unverified\n"
            "Detail.\n"
        )
        with caplog.at_level("WARNING", logger="squadron.review.parsers"):
            parse_review_output(text, "code", {}, diff_files={"src/foo.py"}, cwd=tmp_path)
        assert not [r for r in caplog.records if r.name == "squadron.review.parsers"]


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


# Score-bearing fixture: the minimal shape slice 300 pins — a top-level
# ``score:`` line. NOT the structured-output/JSON shape (that is slice 302).
SCORE_BEARING = """\
## Summary
PASS

score: 87.5

## Findings

### [PASS] Looks good
No issues found.
"""

# Criteria-bearing fixture: a ``criteria:`` YAML-map block of indented
# ``key: <number>`` lines — the same shape ``format_review_markdown`` emits.
CRITERIA_BEARING = """\
## Summary
PASS

score: 88
criteria:
  alignment: 90
  clarity: 80.5
"""


class TestScoreExtraction:
    """Numeric scoring foundation (slice 300): optional score/criteria parse."""

    def test_score_less_real_fixture_is_none(self) -> None:
        """A real existing-template output carries no score (regression guard)."""
        result = parse_review_output(WELL_FORMED_CONCERNS, "code", {})
        assert result.score is None
        assert result.criteria is None
        # Verdict + findings parse exactly as before.
        assert result.verdict == Verdict.CONCERNS
        assert len(result.findings) == 3

    def test_score_bearing_fixture_extracts_float(self) -> None:
        result = parse_review_output(SCORE_BEARING, "code", {})
        assert result.score == 87.5
        # Existing extraction is unaffected.
        assert result.verdict == Verdict.PASS
        assert len(result.findings) == 1

    def test_criteria_bearing_fixture_extracts_map(self) -> None:
        result = parse_review_output(CRITERIA_BEARING, "code", {})
        assert result.criteria == {"alignment": 90.0, "clarity": 80.5}
        assert result.score == 88.0

    def test_parser_never_sets_provenance(self) -> None:
        assert parse_review_output(SCORE_BEARING, "code", {}).provenance is None

    # --- Failure-mode table (each its own assertion) ---

    def test_non_numeric_score_is_none(self) -> None:
        result = parse_review_output("## Summary\nPASS\nscore: high\n", "code", {})
        assert result.score is None

    @pytest.mark.parametrize("token", ["inf", "Inf", "INF", "nan", "NaN", "-inf"])
    def test_non_finite_score_is_none(self, token: str) -> None:
        result = parse_review_output(f"## Summary\nPASS\nscore: {token}\n", "code", {})
        assert result.score is None

    def test_multiple_score_lines_first_wins(self) -> None:
        text = "## Summary\nPASS\nscore: 10\nscore: 20\n"
        assert parse_review_output(text, "code", {}).score == 10.0

    def test_malformed_criteria_is_none_as_whole(self) -> None:
        text = "## Summary\nPASS\ncriteria:\n  alignment: high\n  clarity: 80\n"
        assert parse_review_output(text, "code", {}).criteria is None

    def test_out_of_range_score_is_not_clamped(self) -> None:
        """Range-checking is NOT done here (slice 301's job)."""
        assert parse_review_output("## Summary\nPASS\nscore: 150\n", "code", {}).score == 150.0


class TestVerdictDerivedFromFindings:
    """Verdict recovery when the summary parse loses it (issue #28).

    Finding extraction accepts five heading formats; verdict extraction
    requires one '## Summary' shape. A model that renders recognizable
    findings but reshapes its summary previously wrote a self-contradictory
    document — UNKNOWN alongside a [CONCERN].
    """

    def test_concern_finding_derives_concerns(self) -> None:
        text = "### [CONCERN] GraduatedConfig omits judge-configuration identity\nDetail.\n"
        result = parse_review_output(text, "slice", {})
        assert result.verdict == Verdict.CONCERNS

    def test_fail_dominates_concern(self) -> None:
        text = "### [CONCERN] Lesser problem\nDetail.\n\n### [FAIL] Worse problem\nDetail.\n"
        result = parse_review_output(text, "slice", {})
        assert result.verdict == Verdict.FAIL

    def test_note_only_derives_pass(self) -> None:
        """A NOTE is an observation — deriving CONCERNS would invent severity."""
        text = "### [NOTE] Minor observation\nDetail.\n"
        result = parse_review_output(text, "slice", {})
        assert result.verdict == Verdict.PASS

    def test_stated_verdict_is_never_overridden(self) -> None:
        """Derivation recovers a lost verdict; it never contradicts a stated one."""
        text = "## Summary\nPASS\n\n### [CONCERN] Something\nDetail.\n"
        result = parse_review_output(text, "slice", {})
        assert result.verdict == Verdict.PASS

    def test_no_findings_stays_unknown(self) -> None:
        """Nothing to derive from — UNKNOWN is the honest answer."""
        result = parse_review_output("Unstructured prose with no findings.", "slice", {})
        assert result.verdict == Verdict.UNKNOWN

    def test_derivation_is_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        text = "### [CONCERN] Something actionable\nDetail.\n"
        with caplog.at_level(logging.WARNING):
            result = parse_review_output(text, "slice", {})
        assert result.verdict == Verdict.CONCERNS
        assert "deriving CONCERNS" in caplog.text

    def test_genuine_unknown_is_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        """Previously silent — a failed parse looked like a quiet success."""
        with caplog.at_level(logging.WARNING):
            parse_review_output("Nothing parseable here.", "slice", {})
        assert "no parseable findings" in caplog.text

    def test_issue_28_artifact_shape(self) -> None:
        """The real 322 slice review: findings render, summary reshaped."""
        text = (
            "# Review: slice 322\n\n"
            "**Verdict:** CONCERNS\n\n"  # not under a '## Summary' heading
            "## Findings\n\n"
            "### [CONCERN] GraduatedConfig omits judge-configuration identity\n"
            "location: src/squadron/metrology/models.py:120\n"
            "The record cannot be matched back to the config it graduated.\n"
        )
        result = parse_review_output(text, "slice", {})
        assert result.verdict == Verdict.CONCERNS
        assert len(result.findings) == 1
        assert result.findings[0].severity == Severity.CONCERN


# ---------------------------------------------------------------------------
# Slice 917 Part 3: the finding scan is bounded to real findings (#91, #25)
# ---------------------------------------------------------------------------

_FIXTURES = Path(__file__).parent / "fixtures"

# The template's specimen as a model actually echoes it: the severity
# placeholder resolved to one real value, the placeholder title kept verbatim.
# The literal "[PASS|CONCERN|FAIL]" form matches nothing — a pipe alternation
# is not a severity — so only this substituted shape can produce the #91
# phantom, and only this shape is worth defending against.
_SPECIMEN = """## Summary
PASS

## Findings

### [PASS] Finding title
Description of the finding.
location: src/module.py:12
"""


class TestHeadinglessRealReviews:
    """Two real reviews whose responses carried no '## Findings' heading.

    These parsed to six good findings each before this slice, and a
    heading-required rule would have thrown all twelve away. They are the
    reason the bounded scan falls back to the whole response.
    """

    @pytest.mark.parametrize(
        "fixture_name",
        ["267-headingless-code-response.md", "267-headingless-tasks-response.md"],
    )
    def test_six_findings_survive_without_a_heading(self, fixture_name: str) -> None:
        response = (_FIXTURES / fixture_name).read_text(encoding="utf-8")

        result = parse_review_output(response, "code", {})

        assert len(result.findings) == 6
        assert result.findings_section_located is False
        assert result.finding_scan is not None
        # Every match is a real finding: nothing echoed, nothing fenced.
        assert result.finding_scan.surviving == result.finding_scan.total == 6
        assert result.finding_scan.in_fences == 0

    @pytest.mark.parametrize(
        "fixture_name",
        ["267-headingless-code-response.md", "267-headingless-tasks-response.md"],
    )
    def test_missing_heading_alone_does_not_degrade_the_artifact(self, fixture_name: str) -> None:
        """A missing findings heading must not be what degrades a review.

        These two responses *do* render degraded, but for a reason that
        predates this slice and is unrelated to it: neither carries a
        '## Summary', so the verdict is derived from finding severities
        (#28) and ``fallback_used`` is set. Adding the same summary makes the
        artifact clean while the heading is still absent — which is the fact
        this slice is responsible for.
        """
        from squadron.review.persistence import format_review_markdown

        response = (_FIXTURES / fixture_name).read_text(encoding="utf-8")
        with_summary = f"## Summary\nCONCERNS\n\n{response}"

        result = parse_review_output(with_summary, "code", {})

        assert result.findings_section_located is False
        assert len(result.findings) == 6
        assert result.fallback_used is False
        markdown = format_review_markdown(result, "code")
        # Anchored to line start: these reviews discuss "### Raw Response" in
        # their own finding text, so a bare substring check matches the prose.
        assert not re.search(r"^### Raw Response\s*$", markdown, re.MULTILINE)


class TestFenceMasking:
    def test_specimen_alone_inside_a_fence_yields_nothing(self) -> None:
        response = f"## Summary\nPASS\n\nFormat reminder:\n\n```\n{_SPECIMEN}```\n"

        result = parse_review_output(response, "slice", {})

        assert result.findings == []
        assert result.finding_scan is not None
        assert result.finding_scan.total > 0
        assert result.finding_scan.in_fences == result.finding_scan.total

    def test_tilde_fences_are_masked(self) -> None:
        response = f"## Summary\nPASS\n\n~~~markdown\n{_SPECIMEN}~~~\n"

        result = parse_review_output(response, "slice", {})

        assert result.findings == []

    def test_unclosed_fence_masks_to_end_of_document(self) -> None:
        response = f"## Summary\nPASS\n\n```\n{_SPECIMEN}"

        result = parse_review_output(response, "slice", {})

        assert result.findings == []

    def test_longer_closing_fence_still_closes_the_block(self) -> None:
        """CommonMark allows a closing fence longer than the opener.

        Requiring exact equality treated such a block as unclosed, masked to
        end of document, and silently dropped every finding after it — the
        exact failure this part exists to prevent, on valid input.
        """
        response = (
            "## Summary\nCONCERNS\n\n"
            "```\nechoed format\n````\n\n"
            "## Findings\n\n"
            "### [CONCERN] Real finding\n"
            "Body.\n"
        )

        result = parse_review_output(response, "slice", {})

        assert [f.title for f in result.findings] == ["Real finding"]

    def test_fenced_echo_then_real_findings_yields_only_the_real_ones(self) -> None:
        """The #91 shape: restate the format, then do the work."""
        response = (
            "## Summary\nCONCERNS\n\n"
            f"I will use this structure:\n\n```\n{_SPECIMEN}```\n\n"
            "## Findings\n\n"
            "### [CONCERN] Real problem in the loop\n"
            "The counter is off by one.\n"
            "location: src/squadron/review/parsers.py:10\n\n"
            "### [PASS] Tests cover the change\n"
            "Every branch is exercised.\n"
            "location: tests/review/test_parsers.py:1\n"
        )

        result = parse_review_output(response, "slice", {})

        titles = [f.title for f in result.findings]
        assert titles == ["Real problem in the loop", "Tests cover the change"]
        assert "Finding title" not in titles


class TestSectionBounding:
    def test_unfenced_echo_before_the_heading_is_excluded(self) -> None:
        """An echo the model did not fence is still excluded by the heading."""
        response = (
            "## Summary\nCONCERNS\n\n"
            "### [PASS] Finding title\n"
            "Description of the finding.\n"
            "location: src/module.py:12\n\n"
            "## Findings\n\n"
            "### [CONCERN] Actual first finding\n"
            "Real body.\n\n"
            "### [PASS] Actual second finding\n"
            "Real body.\n"
        )

        result = parse_review_output(response, "slice", {})

        assert [f.title for f in result.findings] == [
            "Actual first finding",
            "Actual second finding",
        ]
        assert result.finding_scan is not None
        assert result.finding_scan.total == 3
        assert result.finding_scan.in_section == 2
        assert result.finding_scan.surviving == 2

    def test_a_following_section_terminates_the_scan(self) -> None:
        response = (
            "## Summary\nCONCERNS\n\n"
            "## Findings\n\n"
            "### [CONCERN] Inside the section\n"
            "Body.\n\n"
            "## Next Steps\n\n"
            "### [PASS] Not a finding at all\n"
            "This is advice, not a finding.\n"
        )

        result = parse_review_output(response, "slice", {})

        assert [f.title for f in result.findings] == ["Inside the section"]

    def test_deeper_heading_does_not_terminate_the_section(self) -> None:
        response = (
            "## Summary\nCONCERNS\n\n"
            "## Findings\n\n"
            "### [CONCERN] First\n"
            "Body.\n\n"
            "#### Sub-detail\n"
            "More body.\n\n"
            "### [PASS] Second\n"
            "Body.\n"
        )

        result = parse_review_output(response, "slice", {})

        assert [f.title for f in result.findings] == ["First", "Second"]

    @pytest.mark.parametrize(
        "heading",
        ["## Findings", "## **Findings**", "## findings:", "## Findings.", "##   Findings   "],
    )
    def test_heading_variants_are_located(self, heading: str) -> None:
        response = (
            f"## Summary\nCONCERNS\n\n"
            "### [PASS] Finding title\n"
            "Echoed specimen.\n\n"
            f"{heading}\n\n"
            "### [CONCERN] The only real finding\n"
            "Body.\n"
        )

        result = parse_review_output(response, "slice", {})

        assert result.findings_section_located is True
        assert [f.title for f in result.findings] == ["The only real finding"]

    def test_heading_at_finding_level_does_not_bound_its_own_findings(self) -> None:
        """A '### Findings' heading cannot contain '### [SEV]' findings.

        The section ends at the next heading of the same or higher level, so a
        same-level findings heading closes before its first finding. Falling
        back to the whole response is the safe outcome — findings are kept,
        not silently dropped — and the digest reports the heading as located.
        """
        response = "## Summary\nCONCERNS\n\n### Findings\n\n### [CONCERN] A real finding\nBody.\n"

        result = parse_review_output(response, "slice", {})

        assert [f.title for f in result.findings] == ["A real finding"]

    def test_summary_section_located_is_recorded(self) -> None:
        with_summary = parse_review_output("## Summary\nPASS\n", "slice", {})
        without_summary = parse_review_output("PASS, all good.\n", "slice", {})

        assert with_summary.summary_section_located is True
        assert without_summary.summary_section_located is False


class TestIssue92ProseOnlyResponse:
    """#92: a full turn of prose review that never emits the required block.

    Not the same failure as #84. The model answered — correct telemetry, a few
    thousand characters of real review — it just answered in prose. Nothing
    raises, so no failure artifact is involved; this is a parse outcome, and
    the existing degraded path already keeps the model's words.

    This slice makes that artifact honest, not recovered: the prose is still
    not turned into findings, because inventing structure from unstructured
    text is how a wrong-but-plausible finding gets manufactured.
    """

    @staticmethod
    def _prose_response() -> str:
        paragraph = (
            "Looking at the task file, the sequencing is sound and every "
            "success criterion traces to at least one task. I would note that "
            "the third part carries more risk than its effort rating suggests. "
        )
        return paragraph * 18

    def test_prose_only_response_parses_to_unknown_with_no_findings(self) -> None:
        response = self._prose_response()
        assert len(response) > 3000

        result = parse_review_output(response, "tasks", {})

        assert result.verdict is Verdict.UNKNOWN
        assert result.findings == []
        assert result.findings_section_located is False
        assert result.summary_section_located is False
        assert result.finding_scan is not None
        assert result.finding_scan.total == 0

    def test_prose_only_artifact_keeps_the_raw_response(self) -> None:
        """The existing degraded path, unchanged — no ProviderError involved."""
        from squadron.review.persistence import format_review_markdown

        result = parse_review_output(self._prose_response(), "tasks", {})

        markdown = format_review_markdown(result, "tasks")

        assert re.search(r"^### Raw Response\s*$", markdown, re.MULTILINE)
        assert "the sequencing is sound" in markdown
        # The artifact says UNKNOWN rather than claiming a clean review.
        assert f"verdict: {Verdict.UNKNOWN.value}" in markdown


# ---------------------------------------------------------------------------
# Slice 917 Part 5: cited line numbers are bounds-checked (#26)
# ---------------------------------------------------------------------------


def _finding_with(location: str) -> str:
    return f"## Summary\nCONCERNS\n\n### [CONCERN] Bug\nlocation: {location}\nDetail.\n"


class TestLocationLineExtraction:
    @pytest.mark.parametrize(
        ("location", "expected"),
        [
            ("src/foo.py:42", 42),
            # The last line of a range is the one that must exist.
            ("src/foo.py:42-50", 50),
            ("src/foo.py#symbol", None),
            ("src/foo.py", None),
            (UNVERIFIED_LOCATION, None),
        ],
    )
    def test_line_extraction(self, location: str, expected: int | None) -> None:
        assert location_line(location) == expected

    def test_location_path_is_unchanged_by_line_extraction(self) -> None:
        """location_path keeps its contract — the findings gate depends on it."""
        assert location_path("src/foo.py:42-50") == "src/foo.py"
        assert location_path("src/foo.py#symbol") == "src/foo.py"


class TestLineBoundsVerification:
    """The tri-state, end to end through parse_review_output."""

    @staticmethod
    def _ten_line_file(tmp_path: Path) -> None:
        (tmp_path / "file.py").write_text("line\n" * 10)

    def test_without_cwd_nothing_is_checked(self, tmp_path: Path) -> None:
        self._ten_line_file(tmp_path)

        result = parse_review_output(_finding_with("file.py:3"), "code", {})

        assert result.findings[0].location_verified is None

    @pytest.mark.parametrize(
        ("location", "expected"),
        [
            ("file.py:7", True),
            ("file.py:10", True),
            ("file.py:3-10", True),
            ("file.py:999999", False),
            ("file.py:11", False),
            ("file.py:3-11", False),
            # Whole-file citations name no line to check.
            ("file.py", None),
            ("file.py#symbol", None),
            (UNVERIFIED_LOCATION, None),
        ],
    )
    def test_tri_state(self, tmp_path: Path, location: str, expected: bool | None) -> None:
        self._ten_line_file(tmp_path)

        result = parse_review_output(_finding_with(location), "code", {}, cwd=tmp_path)

        assert result.findings[0].location_verified is expected

    def test_nonexistent_file_is_false(self, tmp_path: Path) -> None:
        """Verifiably absent — the signature this check exists for."""
        result = parse_review_output(_finding_with("ghost.py:3"), "code", {}, cwd=tmp_path)

        assert result.findings[0].location_verified is False

    def test_issue_91_phantom_citation_is_false(self, tmp_path: Path) -> None:
        """The specimen's own citation, as the #91 phantoms carried it."""
        result = parse_review_output(_finding_with("src/module.py:12"), "code", {}, cwd=tmp_path)

        assert result.findings[0].location_verified is False

    def test_final_line_without_trailing_newline_counts(self, tmp_path: Path) -> None:
        (tmp_path / "file.py").write_text("one\ntwo\nthree")

        result = parse_review_output(_finding_with("file.py:3"), "code", {}, cwd=tmp_path)

        assert result.findings[0].location_verified is True


class TestLineBoundsUncheckableCases:
    """Every case the check cannot run yields None *and* says why.

    A silently unverified citation would be indistinguishable from one that
    was never checked, so each of these must leave an observable signal.
    """

    def test_directory_citation(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        (tmp_path / "pkg").mkdir()

        with caplog.at_level(logging.WARNING, logger="squadron.review.parsers"):
            result = parse_review_output(_finding_with("pkg:1"), "code", {}, cwd=tmp_path)

        assert result.findings[0].location_verified is None
        assert any("Bug" in r.getMessage() for r in caplog.records)

    def test_file_over_the_size_cap(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        (tmp_path / "file.py").write_text("line\n" * 10)
        monkeypatch.setattr("squadron.review.parsers._MAX_LINE_CHECK_BYTES", 10)

        with caplog.at_level(logging.WARNING, logger="squadron.review.parsers"):
            result = parse_review_output(_finding_with("file.py:3"), "code", {}, cwd=tmp_path)

        assert result.findings[0].location_verified is None
        assert any("Bug" in r.getMessage() for r in caplog.records)

    def test_unreadable_file(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        if os.geteuid() == 0:
            pytest.skip("root reads regardless of mode bits")
        target = tmp_path / "file.py"
        target.write_text("line\n" * 10)
        target.chmod(0o000)
        try:
            with caplog.at_level(logging.WARNING, logger="squadron.review.parsers"):
                result = parse_review_output(_finding_with("file.py:3"), "code", {}, cwd=tmp_path)
        finally:
            target.chmod(0o644)

        assert result.findings[0].location_verified is None
        assert any("Bug" in r.getMessage() for r in caplog.records)

    def test_escaping_citation_is_never_opened(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Containment is checked before any open, not after.

        A model-supplied path drives this read. A '../' citation must not
        make the parser read outside the review root even once.
        """
        outside = tmp_path / "outside.py"
        outside.write_text("line\n" * 10)
        root = tmp_path / "root"
        root.mkdir()

        # Patched only after the fixture files exist, so this catches reads by
        # the parser and nothing else.
        def _refuse(*args: object, **kwargs: object) -> None:
            raise AssertionError("the parser opened a file outside the review root")

        monkeypatch.setattr(Path, "open", _refuse)
        with caplog.at_level(logging.WARNING, logger="squadron.review.parsers"):
            result = parse_review_output(_finding_with("../outside.py:1"), "code", {}, cwd=root)

        assert result.findings[0].location_verified is None
        assert any("Bug" in r.getMessage() for r in caplog.records)
