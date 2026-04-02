"""Tests for review persistence — shared formatting and file saving."""

from __future__ import annotations

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


def _make_slice_info() -> SliceInfo:
    return SliceInfo(
        index=146,
        name="review-and-checkpoint-actions",
        slice_name="review-and-checkpoint-actions",
        design_file="project-documents/user/slices/146-slice.md",
        task_files=["146-tasks.review-and-checkpoint-actions.md"],
        arch_file="project-documents/user/architecture/140-arch.md",
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
        parts = md.split("---")
        data = yaml.safe_load(parts[1])
        assert data["docType"] == "review"

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
            result = save_review_file(
                content, "code", "my-slice", 146, cwd=str(tmp_path)
            )
        assert result is None

    def test_json_extension(self, tmp_path: Path) -> None:
        content = '{"verdict": "PASS"}'
        result = save_review_file(
            content, "code", "my-slice", 146, cwd=str(tmp_path), as_json=True
        )
        assert result is not None
        assert result.suffix == ".json"
