"""Tests for review persistence — shared formatting and file saving."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import yaml

from squadron.review.models import (
    ReviewFinding,
    ReviewResult,
    Severity,
    Verdict,
)
from squadron.review.persistence import (
    SliceInfo,
    format_review_markdown,
    save_review_file,
    yaml_escape,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_result(
    verdict: Verdict = Verdict.CONCERNS,
    model: str | None = "claude-opus-4-5",
) -> ReviewResult:
    return ReviewResult(
        verdict=verdict,
        findings=[
            ReviewFinding(
                severity=Severity.CONCERN,
                title="Missing error handling",
                description="No try/except around I/O.",
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
        raw_output="raw review output",
        template_name="code",
        input_files={"input": "file.md"},
        timestamp=datetime(2026, 4, 1, 12, 0, 0),
        model=model,
    )


def _make_slice_info(project: str = "squadron") -> SliceInfo:
    return SliceInfo(
        index=146,
        name="review-and-checkpoint-actions",
        slice_name="review-and-checkpoint-actions",
        design_file="project-documents/user/slices/146-slice.md",
        task_files=["146-tasks.review-and-checkpoint-actions.md"],
        arch_file="project-documents/user/architecture/140-arch.md",
        project=project,
    )


# ---------------------------------------------------------------------------
# yaml_escape
# ---------------------------------------------------------------------------


class TestYamlEscape:
    def test_escapes_backslashes(self) -> None:
        assert yaml_escape("path\\to\\file") == "path\\\\to\\\\file"

    def test_escapes_double_quotes(self) -> None:
        assert yaml_escape('say "hello"') == 'say \\"hello\\"'

    def test_unchanged_when_no_special_chars(self) -> None:
        assert yaml_escape("plain text") == "plain text"

    def test_both_backslash_and_quotes(self) -> None:
        assert yaml_escape('a\\b "c"') == 'a\\\\b \\"c\\"'


# ---------------------------------------------------------------------------
# format_review_markdown
# ---------------------------------------------------------------------------


class TestFormatReviewMarkdown:
    def test_valid_yaml_frontmatter(self) -> None:
        result = _make_result()
        md = format_review_markdown(result, "code", _make_slice_info())
        parts = md.split("---")
        data = yaml.safe_load(parts[1])
        assert data["docType"] == "review"
        assert data["verdict"] == "CONCERNS"
        assert data["aiModel"] == "claude-opus-4-5"

    def test_structured_findings_in_frontmatter(self) -> None:
        result = _make_result()
        md = format_review_markdown(result, "code", _make_slice_info())
        parts = md.split("---")
        data = yaml.safe_load(parts[1])
        assert isinstance(data["findings"], list)
        assert len(data["findings"]) == 2
        f1 = data["findings"][0]
        assert f1["id"] == "F001"
        assert f1["severity"] == "concern"
        assert f1["category"] == "error-handling"
        assert f1["summary"] == "Missing error handling"
        assert f1["location"] == "src/foo.py:10"

    def test_handles_missing_slice_info(self) -> None:
        result = _make_result()
        md = format_review_markdown(result, "code")
        assert "---" in md
        assert "slice: unknown" in md
        assert "project: unknown" in md
        parts = md.split("---")
        data = yaml.safe_load(parts[1])
        assert data["docType"] == "review"

    def test_project_field_reflects_slice_info(self) -> None:
        result = _make_result()
        md = format_review_markdown(result, "code", _make_slice_info(project="context-forge"))
        assert "project: context-forge" in md
        assert "project: squadron" not in md

    def test_project_field_unknown_when_slice_info_none(self) -> None:
        result = _make_result()
        md = format_review_markdown(result, "code", None)
        assert "project: unknown" in md

    def test_prose_body_with_findings(self) -> None:
        result = _make_result()
        md = format_review_markdown(result, "code", _make_slice_info())
        assert "### [CONCERN] Missing error handling" in md
        assert "No try/except around I/O." in md
        assert "### [NOTE] Variable name unclear" in md

    def test_no_findings_shows_placeholder(self) -> None:
        result = ReviewResult(
            verdict=Verdict.PASS,
            findings=[],
            raw_output="all good",
            template_name="code",
            input_files={},
            model="opus",
        )
        md = format_review_markdown(result, "code", _make_slice_info())
        assert "No specific findings." in md
        assert "findings:" not in md

    def test_verdict_override_replaces_raw_verdict(self) -> None:
        """Judge templates leave result.verdict as UNKNOWN by design; the
        caller-supplied threshold-derived verdict must win in both the
        frontmatter and the prose body."""
        result = _make_result()
        result.verdict = Verdict.UNKNOWN
        md = format_review_markdown(result, "code", _make_slice_info(), verdict_override="PASS")
        data = yaml.safe_load(md.split("---")[1])
        assert data["verdict"] == "PASS"
        assert "**Verdict:** PASS" in md
        assert "UNKNOWN" not in md

    def test_no_verdict_override_keeps_raw_verdict(self) -> None:
        result = _make_result()
        md = format_review_markdown(result, "code", _make_slice_info())
        data = yaml.safe_load(md.split("---")[1])
        assert data["verdict"] == "CONCERNS"


class TestFormatReviewMarkdownScore:
    """Numeric scoring foundation (slice 300): frontmatter score/criteria."""

    def test_score_bearing_has_top_level_score_line(self) -> None:
        result = _make_result()
        result.score = 87.5
        md = format_review_markdown(result, "code", _make_slice_info())
        # Greppable top-level score line, per the slice's success criteria.
        assert re.search(r"^score: 87\.5$", md, re.MULTILINE)
        data = yaml.safe_load(md.split("---")[1])
        assert data["score"] == 87.5

    def test_score_less_result_has_no_score_line(self) -> None:
        result = _make_result()
        md = format_review_markdown(result, "code", _make_slice_info())
        assert re.search(r"^score:", md, re.MULTILINE) is None
        assert re.search(r"^criteria:", md, re.MULTILINE) is None

    def test_criteria_present_emits_block(self) -> None:
        result = _make_result()
        result.score = 88.0
        result.criteria = {"alignment": 90.0, "clarity": 80.5}
        md = format_review_markdown(result, "code", _make_slice_info())
        data = yaml.safe_load(md.split("---")[1])
        assert data["criteria"] == {"alignment": 90.0, "clarity": 80.5}

    def test_criteria_absent_has_no_block(self) -> None:
        result = _make_result()
        result.score = 88.0  # score present, criteria absent
        md = format_review_markdown(result, "code", _make_slice_info())
        assert re.search(r"^criteria:", md, re.MULTILINE) is None


# ---------------------------------------------------------------------------
# save_review_file
# ---------------------------------------------------------------------------


class TestSaveReviewFile:
    def test_writes_to_correct_path(self, tmp_path: Path) -> None:
        content = "# Review content"
        result = save_review_file(content, "code", "my-slice", 146, cwd=str(tmp_path))
        assert result is not None
        assert result.name == "146-review.code.my-slice.md"
        assert result.read_text() == content

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        cwd = tmp_path / "deep" / "nested"
        content = "# Review"
        result = save_review_file(content, "slice", "test", 100, cwd=str(cwd))
        assert result is not None
        assert result.exists()

    def test_returns_none_on_write_failure(self, tmp_path: Path) -> None:
        content = "# Review"
        with patch.object(Path, "write_text", side_effect=OSError("disk full")):
            result = save_review_file(content, "code", "my-slice", 146, cwd=str(tmp_path))
        assert result is None

    def test_json_extension(self, tmp_path: Path) -> None:
        content = '{"verdict": "PASS"}'
        result = save_review_file(content, "code", "my-slice", 146, cwd=str(tmp_path), as_json=True)
        assert result is not None
        assert result.suffix == ".json"
