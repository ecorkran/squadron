"""Tests for structured findings in review frontmatter formatting."""

from __future__ import annotations

from datetime import datetime

import yaml

from squadron.cli.commands.review import (
    SliceInfo,
    _format_review_markdown,
    _yaml_escape,
)
from squadron.review.models import (
    ReviewFinding,
    ReviewResult,
    Severity,
    Verdict,
)

SLICE_INFO: SliceInfo = {
    "index": 143,
    "name": "Structured Review Findings",
    "slice_name": "structured-review-findings",
    "design_file": "project-documents/user/slices/143-slice.structured-review-findings.md",
    "task_files": ["143-tasks.structured-review-findings.md"],
    "arch_file": "project-documents/user/architecture/140-arch.pipeline-foundation.md",
}


def _make_result_with_structured_findings() -> ReviewResult:
    return ReviewResult(
        verdict=Verdict.CONCERNS,
        findings=[
            ReviewFinding(
                severity=Severity.CONCERN,
                title="Missing error handling",
                description="No try/except.",
                file_ref="src/foo.py:10",
                category="error-handling",
                location="src/foo.py:10",
            ),
            ReviewFinding(
                severity=Severity.NOTE,
                title="Variable name unclear",
                description="Variable x is vague.",
                category="naming",
            ),
        ],
        raw_output="raw",
        template_name="code",
        input_files={},
        timestamp=datetime(2026, 3, 30, 12, 0, 0),
        model="opus",
    )


def _make_result_no_findings() -> ReviewResult:
    return ReviewResult(
        verdict=Verdict.PASS,
        findings=[],
        raw_output="raw",
        template_name="code",
        input_files={},
        timestamp=datetime(2026, 3, 30, 12, 0, 0),
        model="opus",
    )


class TestFrontmatterFindings:
    """Test structured findings block in YAML frontmatter."""

    def test_findings_block_present(self) -> None:
        result = _make_result_with_structured_findings()
        md = _format_review_markdown(result, "code", SLICE_INFO)
        assert "findings:" in md

    def test_finding_has_required_fields(self) -> None:
        result = _make_result_with_structured_findings()
        md = _format_review_markdown(result, "code", SLICE_INFO)
        assert "  - id: F001" in md
        assert "    severity: concern" in md
        assert "    category: error-handling" in md
        assert '    summary: "Missing error handling"' in md

    def test_finding_with_location(self) -> None:
        result = _make_result_with_structured_findings()
        md = _format_review_markdown(result, "code", SLICE_INFO)
        assert "    location: src/foo.py:10" in md

    def test_finding_without_location_omits_field(self) -> None:
        result = _make_result_with_structured_findings()
        md = _format_review_markdown(result, "code", SLICE_INFO)
        # Second finding (F002) has no location — check it's not emitted
        lines = md.split("\n")
        f002_idx = next(i for i, l in enumerate(lines) if "id: F002" in l)
        # Lines between F002 and the closing --- should not have location
        f002_block = []
        for line in lines[f002_idx:]:
            if line.strip() == "---":
                break
            if line.startswith("  - id:") and "F002" not in line:
                break
            f002_block.append(line)
        assert not any("location:" in l for l in f002_block)

    def test_summary_with_double_quotes_escaped(self) -> None:
        result = ReviewResult(
            verdict=Verdict.CONCERNS,
            findings=[
                ReviewFinding(
                    severity=Severity.CONCERN,
                    title='Variable "x" unclear',
                    description="Rename it.",
                    category="naming",
                ),
            ],
            raw_output="raw",
            template_name="code",
            input_files={},
            timestamp=datetime(2026, 3, 30, 12, 0, 0),
            model="opus",
        )
        md = _format_review_markdown(result, "code", SLICE_INFO)
        assert r'summary: "Variable \"x\" unclear"' in md

    def test_frontmatter_is_valid_yaml(self) -> None:
        result = _make_result_with_structured_findings()
        md = _format_review_markdown(result, "code", SLICE_INFO)
        # Extract frontmatter between --- markers
        parts = md.split("---")
        frontmatter_text = parts[1]
        data = yaml.safe_load(frontmatter_text)
        assert data["docType"] == "review"
        assert data["verdict"] == "CONCERNS"
        assert isinstance(data["findings"], list)
        assert len(data["findings"]) == 2
        assert data["findings"][0]["id"] == "F001"
        assert data["findings"][0]["severity"] == "concern"

    def test_no_findings_block_when_empty(self) -> None:
        result = _make_result_no_findings()
        md = _format_review_markdown(result, "code", SLICE_INFO)
        assert "findings:" not in md

    def test_prose_body_unchanged(self) -> None:
        result = _make_result_with_structured_findings()
        md = _format_review_markdown(result, "code", SLICE_INFO)
        assert "### [CONCERN] Missing error handling" in md
        assert "### [NOTE] Variable name unclear" in md


class TestYamlEscape:
    """Test _yaml_escape helper."""

    def test_escapes_double_quotes(self) -> None:
        assert _yaml_escape('hello "world"') == 'hello \\"world\\"'

    def test_no_quotes_unchanged(self) -> None:
        assert _yaml_escape("hello world") == "hello world"

    def test_escapes_backslash(self) -> None:
        assert _yaml_escape("path\\to\\file") == "path\\\\to\\\\file"
