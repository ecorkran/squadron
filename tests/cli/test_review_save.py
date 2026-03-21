"""Tests for review file auto-save functionality."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from squadron.cli.commands.review import (
    SliceInfo,
    _format_review_markdown,
    _save_review_file,
)
from squadron.review.models import (
    ReviewFinding,
    ReviewResult,
    Severity,
    Verdict,
)


def _make_result(
    verdict: Verdict = Verdict.CONCERNS,
) -> ReviewResult:
    """Create a sample ReviewResult for testing."""
    return ReviewResult(
        verdict=verdict,
        findings=[
            ReviewFinding(
                severity=Severity.CONCERN,
                title="Test concern",
                description="A test finding.",
                file_ref="src/foo.py:10",
            ),
            ReviewFinding(
                severity=Severity.PASS,
                title="Looks good",
                description=None,
                file_ref=None,
            ),
        ],
        raw_output="raw review text",
        template_name="arch",
        input_files={"input": "slice.md", "against": "arch.md"},
        timestamp=datetime(2026, 3, 21, 12, 0, 0),
        model="opus",
    )


SLICE_INFO: SliceInfo = {
    "index": 118,
    "name": "Composed Workflows",
    "slice_name": "composed-workflows",
    "design_file": ("project-documents/user/slices/118-slice.composed-workflows.md"),
    "task_files": ["118-tasks.composed-workflows.md"],
    "arch_file": ("project-documents/user/architecture/100-arch.orchestration-v2.md"),
}


def test_format_review_markdown_has_frontmatter() -> None:
    """Markdown output includes YAML frontmatter with correct fields."""
    result = _make_result()
    md = _format_review_markdown(result, "arch", SLICE_INFO)
    assert "---" in md
    assert "docType: review" in md
    assert "reviewType: arch" in md
    assert "slice: composed-workflows" in md
    assert "project: squadron" in md
    assert "verdict: CONCERNS" in md
    assert "dateCreated: 20260321" in md


def test_format_review_markdown_has_findings() -> None:
    """Markdown output includes findings with severity badges."""
    result = _make_result()
    md = _format_review_markdown(result, "arch", SLICE_INFO)
    assert "### [CONCERN] Test concern" in md
    assert "A test finding." in md
    assert "### [PASS] Looks good" in md


def test_save_review_file_writes_markdown(tmp_path: Path) -> None:
    """Saves a markdown review file with correct name."""
    result = _make_result()
    path = _save_review_file(result, "arch", SLICE_INFO, reviews_dir=tmp_path)
    assert path.exists()
    assert path.name == "118-review.arch.composed-workflows.md"
    content = path.read_text()
    assert "docType: review" in content
    assert "verdict: CONCERNS" in content


def test_save_review_file_writes_json(tmp_path: Path) -> None:
    """Saves a JSON review file when as_json=True."""
    result = _make_result()
    path = _save_review_file(
        result, "arch", SLICE_INFO, as_json=True, reviews_dir=tmp_path
    )
    assert path.exists()
    assert path.name == "118-review.arch.composed-workflows.json"
    data = json.loads(path.read_text())
    assert data["verdict"] == "CONCERNS"
    assert len(data["findings"]) == 2


def test_save_review_file_overwrites_existing(tmp_path: Path) -> None:
    """Re-saving overwrites the existing file."""
    existing = tmp_path / "118-review.arch.composed-workflows.md"
    existing.write_text("old content")

    result = _make_result(verdict=Verdict.PASS)
    _save_review_file(result, "arch", SLICE_INFO, reviews_dir=tmp_path)

    content = existing.read_text()
    assert "old content" not in content
    assert "verdict: PASS" in content


def test_save_review_file_creates_directory(tmp_path: Path) -> None:
    """Creates the reviews directory if it doesn't exist."""
    reviews_dir = tmp_path / "nested" / "reviews"
    assert not reviews_dir.exists()

    result = _make_result()
    path = _save_review_file(result, "arch", SLICE_INFO, reviews_dir=reviews_dir)

    assert reviews_dir.exists()
    assert path.exists()
