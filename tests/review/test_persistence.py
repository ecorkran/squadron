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

from squadron.documents.frontmatter import read_frontmatter
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

    def test_location_with_colon_space_round_trips(self, tmp_path: Path) -> None:
        """The corruption class this slice exists to close.

        A location like a document anchor (`Slice design: Implementation
        Details`) contains a colon-space, which makes unquoted YAML read it
        as a nested mapping and fail to parse. Quoting it must keep the
        original string intact end to end.
        """
        colon_space_location = "Slice design: Implementation Details"
        result = ReviewResult(
            verdict=Verdict.CONCERNS,
            findings=[
                ReviewFinding(
                    severity=Severity.CONCERN,
                    title="Stale reference",
                    description="Points at the wrong section.",
                    category="accuracy",
                    location=colon_space_location,
                )
            ],
            raw_output="raw",
            template_name="slice",
            input_files={"input": "file.md"},
            timestamp=datetime(2026, 4, 1, 12, 0, 0),
        )
        md = format_review_markdown(result, "slice", _make_slice_info())
        doc = tmp_path / "probe.md"
        doc.write_text(md, encoding="utf-8")

        data = read_frontmatter(doc)

        assert data is not None
        findings = cast("list[dict[str, object]]", data["findings"])
        assert findings[0]["location"] == colon_space_location

    def test_location_with_embedded_quote_round_trips(self, tmp_path: Path) -> None:
        quoted_location = 'anchor "with quotes" inside'
        result = ReviewResult(
            verdict=Verdict.CONCERNS,
            findings=[
                ReviewFinding(
                    severity=Severity.CONCERN,
                    title="Stale reference",
                    description="Points at the wrong section.",
                    category="accuracy",
                    location=quoted_location,
                )
            ],
            raw_output="raw",
            template_name="slice",
            input_files={"input": "file.md"},
            timestamp=datetime(2026, 4, 1, 12, 0, 0),
        )
        md = format_review_markdown(result, "slice", _make_slice_info())
        doc = tmp_path / "probe.md"
        doc.write_text(md, encoding="utf-8")

        data = read_frontmatter(doc)

        assert data is not None
        findings = cast("list[dict[str, object]]", data["findings"])
        assert findings[0]["location"] == quoted_location

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


# ---------------------------------------------------------------------------
# Overwrite guard (slice 306 Part D)
# ---------------------------------------------------------------------------


_MARKER = "\n## Hand note — added after the review was authored\n"


class TestArchiveOnOverwrite:
    """A re-review must never silently destroy hand-written content."""

    def test_prior_content_is_archived_byte_for_byte(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        path = save_review_result(_make_result(), "code", _make_slice_info())
        edited = path.read_text() + _MARKER
        path.write_text(edited)

        path = save_review_result(_make_result(verdict=Verdict.PASS), "code", _make_slice_info())

        archived = path.parent / "archive" / path.name
        assert archived.read_text() == edited
        assert _MARKER in archived.read_text()
        # The new save landed on the original path.
        assert _frontmatter(path.read_text())["verdict"] == "PASS"
        assert _MARKER not in path.read_text()

    def test_first_save_creates_no_archive_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        path = save_review_result(_make_result(), "code", _make_slice_info())
        assert not (path.parent / "archive").exists()

    def test_unwritable_archive_dir_aborts_and_leaves_original_intact(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Copy cannot be created — a file sits where the directory must go."""
        reviews = tmp_path / "project-documents" / "user" / "reviews"
        reviews.mkdir(parents=True)
        path = reviews / "146-review.code.my-slice.md"
        path.write_text("original content")
        (reviews / "archive").write_text("not a directory")

        with caplog.at_level(logging.ERROR, logger="squadron.review.persistence"):
            result = save_review_file("replacement content", "code", "my-slice", 146, cwd=str(tmp_path))

        assert result is None
        assert path.read_text() == "original content"
        assert any("could not archive" in r.message for r in caplog.records)

    def test_unverifiable_copy_aborts_and_leaves_original_intact(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Copy succeeds but reads back wrong — a distinct path from no copy.

        The archive file really is written here; only the verification read
        disagrees, which is the corruption case the guard exists to catch.
        """
        reviews = tmp_path / "project-documents" / "user" / "reviews"
        reviews.mkdir(parents=True)
        path = reviews / "146-review.code.my-slice.md"
        path.write_text("original content")

        real_read_bytes = Path.read_bytes
        calls: list[Path] = []

        def _corrupt_read_back(self: Path) -> bytes:
            calls.append(self)
            data = real_read_bytes(self)
            # First call reads the original; the second is the verification
            # read of the freshly written archive copy.
            return data if len(calls) == 1 else data + b"corrupted"

        with (
            caplog.at_level(logging.ERROR, logger="squadron.review.persistence"),
            patch.object(Path, "read_bytes", _corrupt_read_back),
        ):
            result = save_review_file("replacement content", "code", "my-slice", 146, cwd=str(tmp_path))

        assert result is None
        assert path.read_text() == "original content"
        # The copy itself was made — this is verification failure, not a
        # failure to write.
        assert (reviews / "archive" / path.name).read_text() == "original content"
        assert any("does not match the original" in r.message for r in caplog.records)

    def test_save_review_result_raises_rather_than_overwriting(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The CLI path fails loudly; its signature has no None to return."""
        monkeypatch.chdir(tmp_path)
        path = save_review_result(_make_result(), "code", _make_slice_info())
        edited = path.read_text() + _MARKER
        path.write_text(edited)

        with (
            patch("squadron.review.persistence.archive_existing_review", return_value=False),
            pytest.raises(OSError, match="refusing to overwrite"),
        ):
            save_review_result(_make_result(), "code", _make_slice_info())

        assert path.read_text() == edited
