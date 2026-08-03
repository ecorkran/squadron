"""Tests for review persistence — shared formatting and file saving."""

from __future__ import annotations

import logging
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import cast
from unittest.mock import patch

import pytest
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
    save_review_result,
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


class TestFormatReviewMarkdownRevisionNumber:
    """Slice 911 Part B — revision_number is emitted only when supplied."""

    def test_omitted_when_not_supplied(self) -> None:
        result = _make_result()
        md = format_review_markdown(result, "code", _make_slice_info())
        data = yaml.safe_load(md.split("---")[1])
        assert "revision_number" not in data

    def test_present_with_supplied_value(self) -> None:
        result = _make_result()
        md = format_review_markdown(result, "code", _make_slice_info(), revision_number=2)
        data = yaml.safe_load(md.split("---")[1])
        assert data["revision_number"] == 2


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


# ---------------------------------------------------------------------------
# reviewedSha stamp (slice 306 Part A)
# ---------------------------------------------------------------------------


def _frontmatter(md: str) -> dict[str, object]:
    """Parse a rendered review's YAML frontmatter."""
    data = yaml.safe_load(md.split("---")[1])
    assert isinstance(data, dict)
    return cast("dict[str, object]", data)


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """A temporary git repo with one commit, so HEAD resolves."""
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True, check=True
    )
    (tmp_path / "README.md").write_text("init")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True, check=True)
    return tmp_path


class TestReviewedShaStamp:
    def test_stamped_when_supplied(self) -> None:
        md = format_review_markdown(_make_result(), "code", _make_slice_info(), reviewed_sha="abc123")
        assert "reviewedSha: abc123" in md
        assert _frontmatter(md)["reviewedSha"] == "abc123"

    def test_key_absent_when_not_supplied(self) -> None:
        """Absent, not ``null`` — a fabricated anchor is worse than none."""
        md = format_review_markdown(_make_result(), "code", _make_slice_info())
        assert "reviewedSha" not in md
        assert "reviewedSha" not in _frontmatter(md)

    def test_save_review_result_stamps_head(
        self, git_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(git_repo)
        path = save_review_result(_make_result(), "code", _make_slice_info())

        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=git_repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        assert _frontmatter(path.read_text())["reviewedSha"] == head

    def test_git_unavailable_omits_key_and_warns(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """``run_git`` returning None means git could not be invoked at all."""
        monkeypatch.chdir(tmp_path)
        with (
            caplog.at_level(logging.WARNING, logger="squadron.review.persistence"),
            patch("squadron.review.persistence.run_git", return_value=None),
        ):
            path = save_review_result(_make_result(), "code", _make_slice_info())

        assert "reviewedSha" not in _frontmatter(path.read_text())
        assert any("reviewedSha will not be stamped" in r.message for r in caplog.records)

    def test_git_nonzero_omits_key_and_warns(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """git ran and refused — a different failure from git being absent."""
        monkeypatch.chdir(tmp_path)
        refused = subprocess.CompletedProcess(
            args=["git", "rev-parse", "HEAD"], returncode=128, stdout="", stderr="not a repository"
        )
        with (
            caplog.at_level(logging.WARNING, logger="squadron.review.persistence"),
            patch("squadron.review.persistence.run_git", return_value=refused),
        ):
            path = save_review_result(_make_result(), "code", _make_slice_info())

        assert "reviewedSha" not in _frontmatter(path.read_text())
        assert any("reviewedSha will not be stamped" in r.message for r in caplog.records)

    def test_findings_block_shape_is_unchanged_by_the_stamp(self) -> None:
        """Bind the frontmatter findings shape ``records_from_frontmatter`` reads.

        Part B parses this block out of real review artifacts. Nothing else
        pins its shape, so a change to ``format_review_markdown`` could alter
        it silently and only surface as a broken resolve against production
        files. Rendered through the real formatter, with the new parameter set.
        """
        result = ReviewResult(
            verdict=Verdict.FAIL,
            findings=[
                ReviewFinding(
                    severity=Severity.FAIL,
                    title="Unhandled write failure",
                    description="write_text can raise.",
                    category="error-handling",
                    location="src/a.py:10",
                ),
                ReviewFinding(
                    severity=Severity.CONCERN,
                    title="Duplicated parse",
                    description="Two parsers.",
                    category="duplication",
                    location="src/b.py:42",
                ),
                ReviewFinding(
                    severity=Severity.NOTE,
                    title="Vague name",
                    description="x is vague.",
                    category="naming",
                ),
            ],
            raw_output="raw",
            template_name="code",
            input_files={"input": "file.md"},
            timestamp=datetime(2026, 4, 1, 12, 0, 0),
            model="claude-opus-4-5",
        )
        md = format_review_markdown(result, "code", _make_slice_info(), reviewed_sha="deadbeef")
        findings = _frontmatter(md)["findings"]

        assert isinstance(findings, list)
        assert len(findings) == 3
        assert [f["severity"] for f in findings] == ["fail", "concern", "note"]  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
        for entry in findings:  # pyright: ignore[reportUnknownVariableType]
            assert set(entry) >= {"id", "severity", "category", "summary"}  # pyright: ignore[reportUnknownArgumentType]
        # ``location`` is emitted only when the finding carries one.
        assert findings[0]["location"] == "src/a.py:10"  # pyright: ignore[reportUnknownVariableType]
        assert "location" not in findings[2]  # pyright: ignore[reportUnknownArgumentType]
