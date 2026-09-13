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
from squadron.documents.schema import DocType, DocumentStatus
from squadron.providers.errors import ProviderError
from squadron.review.models import (
    FindingScanCounts,
    ReviewFinding,
    ReviewResult,
    Severity,
    Verdict,
)
from squadron.review.persistence import (
    REVIEWS_DIR,
    SliceInfo,
    format_provider_failure_markdown,
    format_review_markdown,
    save_provider_failure,
    save_review_file,
    save_review_result,
    yaml_escape,
)
from squadron.tools import SuppressionReason

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


class TestFormatReviewMarkdownToolTelemetry:
    """Slice 265: tool use must be visible in the artifact people actually read."""

    def test_tool_bearing_review_emits_telemetry(self) -> None:
        result = _make_result()
        result.tools_given = ["read_file", "grep"]
        result.tool_calls_made = 4
        md = format_review_markdown(result, "code", _make_slice_info())
        data = yaml.safe_load(md.split("---")[1])
        assert data["toolsGiven"] == ["read_file", "grep"]
        assert data["toolCallsMade"] == 4

    def test_offered_but_unused_is_distinct_from_never_offered(self) -> None:
        """tool_calls_made: 0 with a populated list is a real state, not an absent one."""
        result = _make_result()
        result.tools_given = ["read_file"]
        result.tool_calls_made = 0
        md = format_review_markdown(result, "code", _make_slice_info())
        data = yaml.safe_load(md.split("---")[1])
        assert data["toolsGiven"] == ["read_file"]
        assert data["toolCallsMade"] == 0

    def test_tool_less_review_omits_the_keys_entirely(self) -> None:
        result = _make_result()
        md = format_review_markdown(result, "code", _make_slice_info())
        assert re.search(r"^toolsGiven:", md, re.MULTILINE) is None
        assert re.search(r"^toolCallsMade:", md, re.MULTILINE) is None


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


class TestDegradedParseIsVisible:
    """A degraded parse must never render as a clean review (issue #72)."""

    @staticmethod
    def _degraded(verdict: Verdict = Verdict.CONCERNS) -> ReviewResult:
        """A verdict that parsed while every finding failed to."""
        return ReviewResult(
            verdict=verdict,
            findings=[],
            raw_output="1. The retry loop never terminates.\n2. The jail check is bypassable.",
            template_name="code",
            input_files={"input": "file.md"},
            timestamp=datetime(2026, 4, 1, 12, 0, 0),
            model="claude-sonnet-5",
            fallback_used=True,
        )

    def test_degraded_review_does_not_claim_no_findings(self) -> None:
        md = format_review_markdown(self._degraded(), "code", _make_slice_info())
        assert "No specific findings." not in md
        assert "degraded" in md.lower()

    def test_degraded_review_points_at_the_raw_response(self) -> None:
        md = format_review_markdown(self._degraded(), "code", _make_slice_info())
        assert "Raw Response" in md

    def test_genuinely_clean_review_is_unchanged(self) -> None:
        """A real no-findings review must not be mislabeled as degraded."""
        clean = ReviewResult(
            verdict=Verdict.PASS,
            findings=[],
            raw_output="Looks good.",
            template_name="code",
            input_files={"input": "file.md"},
            timestamp=datetime(2026, 4, 1, 12, 0, 0),
            model="claude-sonnet-5",
            fallback_used=False,
        )
        md = format_review_markdown(clean, "code", _make_slice_info())
        assert "No specific findings." in md
        assert "degraded" not in md.lower()

    def test_json_output_carries_the_degraded_flag(self) -> None:
        assert self._degraded().to_dict()["fallback_used"] is True

    def test_json_output_of_clean_review_is_not_degraded(self) -> None:
        assert _make_result().to_dict()["fallback_used"] is False


class TestArchiveIsNonDestructive:
    """A run of bad reviews must not walk a good one out of existence (#73)."""

    def test_second_overwrite_preserves_the_first_archived_copy(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        path = save_review_result(_make_result(), "code", _make_slice_info())
        good = path.read_text() + "\n## the good review\n"
        path.write_text(good)

        # First overwrite: the good copy lands in the stable archive slot.
        save_review_result(_make_result(verdict=Verdict.PASS), "code", _make_slice_info())
        archived = path.parent / "archive" / path.name
        assert "the good review" in archived.read_text()

        # Second overwrite: the stable slot is reused, but the good copy must
        # survive under a timestamped generation rather than being destroyed.
        save_review_result(_make_result(verdict=Verdict.FAIL), "code", _make_slice_info())

        generations = list((path.parent / "archive").glob(f"{path.stem}.*{path.suffix}"))
        surviving = [p for p in generations if "the good review" in p.read_text()]
        assert surviving, "the good review was destroyed by a second overwrite"


class TestFormatReviewMarkdownSuppressionReason:
    """Slice 266: suppression is the third state slice 265's two fields cannot express."""

    def test_three_tool_states_are_distinguishable(self) -> None:
        """offered-and-used, offered-and-unused, and suppressed must not collapse."""
        used = _make_result()
        used.tools_given = ["read_file"]
        used.tool_calls_made = 3

        unused = _make_result()
        unused.tools_given = ["read_file"]
        unused.tool_calls_made = 0

        suppressed = _make_result()
        suppressed.tools_suppressed_reason = SuppressionReason.MODEL_CAPABILITY.value

        frames = [
            yaml.safe_load(format_review_markdown(r, "code", _make_slice_info()).split("---")[1])
            for r in (used, unused, suppressed)
        ]
        assert frames[0]["toolCallsMade"] == 3
        assert frames[1]["toolCallsMade"] == 0
        assert "toolsGiven" not in frames[2]
        assert frames[2]["toolsSuppressedReason"] == SuppressionReason.MODEL_CAPABILITY.value
        # And the suppressed frame is not mistakable for either of the others.
        assert "toolsSuppressedReason" not in frames[0]
        assert "toolsSuppressedReason" not in frames[1]

    def test_reasons_are_distinct_in_persisted_text(self) -> None:
        """SC4: capability denial and --no-tools must be told apart from the field alone."""
        capability = _make_result()
        capability.tools_suppressed_reason = SuppressionReason.MODEL_CAPABILITY.value
        run = _make_result()
        run.tools_suppressed_reason = SuppressionReason.RUN_SUPPRESSED.value

        rendered = [
            yaml.safe_load(format_review_markdown(r, "code", _make_slice_info()).split("---")[1])[
                "toolsSuppressedReason"
            ]
            for r in (capability, run)
        ]
        assert rendered[0] != rendered[1]

    def test_ungated_review_artifact_is_unchanged(self) -> None:
        """A run that never declared tools must not grow the field."""
        result = _make_result()
        md = format_review_markdown(result, "code", _make_slice_info())
        assert re.search(r"^toolsSuppressedReason:", md, re.MULTILINE) is None

    def test_to_dict_carries_the_reason_and_omits_it_otherwise(self) -> None:
        """Both persistence forms, not JSON only — issue #72's shape."""
        suppressed = _make_result()
        suppressed.tools_suppressed_reason = SuppressionReason.RUN_SUPPRESSED.value
        assert suppressed.to_dict()["tools_suppressed_reason"] == SuppressionReason.RUN_SUPPRESSED.value
        assert "tools_suppressed_reason" not in _make_result().to_dict()


# ---------------------------------------------------------------------------
# Degraded artifacts embed the raw response (#61, design D3)
# ---------------------------------------------------------------------------


class TestDegradedRawResponse:
    """A degraded review's artifact is often the only surviving record of the output.

    Before this, the raw response reached the artifact only inside the ``-vv`` prompt
    appendix, so a degraded review run at the default verbosity kept nothing.
    """

    _RAW = "The model rambled without a summary or findings."

    def _degraded_unknown(self) -> ReviewResult:
        return ReviewResult(
            verdict=Verdict.UNKNOWN,
            findings=[],
            raw_output=self._RAW,
            template_name="code",
            input_files={"input": "file.md"},
            timestamp=datetime(2026, 4, 1, 12, 0, 0),
            model="claude-opus-4-5",
        )

    def _fallback_used(self) -> ReviewResult:
        result = self._degraded_unknown()
        result.verdict = Verdict.CONCERNS
        result.fallback_used = True
        return result

    def test_unknown_verdict_embeds_raw_response_at_verbosity_zero(self) -> None:
        md = format_review_markdown(self._degraded_unknown(), "code", _make_slice_info())

        assert "### Raw Response" in md.splitlines()
        assert self._RAW in md

    def test_fallback_used_embeds_raw_response_at_verbosity_zero(self) -> None:
        md = format_review_markdown(self._fallback_used(), "code", _make_slice_info())

        assert "### Raw Response" in md.splitlines()
        assert self._RAW in md

    def test_degraded_artifact_renders_raw_response_exactly_once(self) -> None:
        """With the -vv appendix present, both sections must not each print it."""
        result = self._degraded_unknown()
        result.system_prompt = "Review the diff."
        result.user_prompt = "diff"

        md = format_review_markdown(result, "code", _make_slice_info())

        # Count real section headings, not the backticked reference in the body prose.
        headings = [line for line in md.splitlines() if line == "### Raw Response"]
        assert len(headings) == 1
        assert md.count(self._RAW) == 1

    def test_judge_with_score_does_not_embed_its_raw_response(self) -> None:
        """A judge's raw parse is always UNKNOWN; its verdict arrives as an override.

        Keying on the raw parse would embed every judge's response in every artifact.
        """
        result = self._degraded_unknown()
        result.score = 8.5

        md = format_review_markdown(result, "judge", _make_slice_info(), verdict_override="PASS")

        assert "### Raw Response" not in md.splitlines()
        assert self._RAW not in md

    def test_unknown_verdict_does_not_claim_no_specific_findings(self) -> None:
        md = format_review_markdown(self._degraded_unknown(), "code", _make_slice_info())

        assert "No specific findings." not in md
        assert "## Findings Not Parsed" in md

    def test_degraded_body_no_longer_promises_vv(self) -> None:
        """The old text pointed at a section only a -vv run produced — it was false."""
        md = format_review_markdown(self._fallback_used(), "code", _make_slice_info())

        assert "-vv" not in md

    def test_clean_pass_artifact_is_byte_identical_to_the_pre_change_snapshot(self) -> None:
        """SC4's other half: a non-degraded artifact must not shift by one byte.

        The fixture is regenerated only when a change to the clean path is *intended*;
        any other drift fails here. Last regenerated for slice 918, which added the four
        stop-reason evidence lines to the Run Digest.
        """
        result = ReviewResult(
            verdict=Verdict.PASS,
            findings=[],
            raw_output="The model said the code is clean.",
            template_name="code",
            input_files={"input": "file.md"},
            timestamp=datetime(2026, 4, 1, 12, 0, 0),
            model="claude-opus-4-5",
        )

        md = format_review_markdown(result, "code", _make_slice_info())

        snapshot = Path(__file__).parent / "fixtures" / "clean_pass_artifact.md"
        assert md == snapshot.read_text()


# ---------------------------------------------------------------------------
# Slice 917 Part 4: a provider failure leaves an artifact (#84)
# ---------------------------------------------------------------------------

_FAILURE_MESSAGE = (
    "Model returned an empty final turn (finish_reason='length', "
    "reasoning_chars=1200); no response to deliver."
)


def _failure_slice_info() -> SliceInfo:
    return {
        "slice_name": "review-artifact-integrity",
        "index": 917,
        "project": "squadron",
        "design_file": "project-documents/user/slices/917-slice.md",
    }


class TestProviderFailureArtifact:
    def test_states_the_failure_and_claims_no_findings(self) -> None:
        """The artifact must not read as a review that found nothing."""
        exc = ProviderError(_FAILURE_MESSAGE, tool_calls_made=0)

        markdown = format_provider_failure_markdown(exc, "slice", _failure_slice_info(), model="glm53")

        assert f"docType: {DocType.REVIEW}" in markdown
        assert f"verdict: {Verdict.UNKNOWN.value}" in markdown
        assert f"status: {DocumentStatus.COMPLETE}" in markdown
        assert "## Provider Failure" in markdown
        assert "## Findings" not in markdown
        # The provider's own evidence survives to the artifact.
        assert "finish_reason='length'" in markdown
        assert "reasoning_chars=1200" in markdown

    def test_tool_telemetry_distinguishes_offered_from_never_offered(self) -> None:
        exc = ProviderError(_FAILURE_MESSAGE, tool_calls_made=2)

        offered = format_provider_failure_markdown(
            exc, "slice", _failure_slice_info(), tools_given=["read_file"]
        )
        never_offered = format_provider_failure_markdown(
            exc, "slice", _failure_slice_info(), tools_given=None
        )

        assert "toolsGiven: [read_file]" in offered
        assert "toolCallsMade: 2" in offered
        assert "toolsGiven" not in never_offered
        assert "toolCallsMade" not in never_offered

    def test_offered_but_unused_is_its_own_state(self) -> None:
        """'Given tools, said nothing' is the case slice 265 D5 exists for."""
        exc = ProviderError(_FAILURE_MESSAGE, tool_calls_made=0)

        markdown = format_provider_failure_markdown(
            exc, "slice", _failure_slice_info(), tools_given=["read_file", "grep"]
        )

        assert "toolsGiven: [read_file, grep]" in markdown
        assert "toolCallsMade: 0" in markdown

    def test_missing_count_renders_as_zero_not_absent(self) -> None:
        exc = ProviderError(_FAILURE_MESSAGE)

        markdown = format_provider_failure_markdown(
            exc, "slice", _failure_slice_info(), tools_given=["read_file"]
        )

        assert "toolCallsMade: 0" in markdown

    def test_no_slice_info_does_not_fabricate_a_slice_index(self) -> None:
        exc = ProviderError(_FAILURE_MESSAGE)

        markdown = format_provider_failure_markdown(exc, "code", None)

        assert "slice 0" not in markdown
        assert "# Review: code" in markdown
        assert "slice: unknown" in markdown

    def test_saved_failure_archives_the_prior_artifact(self, tmp_path: Path) -> None:
        """Fail-closed: the live slot holds the failure, not a stale verdict.

        Leaving the previous artifact in place would let the next gate read a
        passing verdict from a run that never happened.
        """
        reviews = tmp_path / REVIEWS_DIR
        reviews.mkdir(parents=True)
        live = reviews / "917-review.slice.review-artifact-integrity.md"
        live.write_text("---\nverdict: PASS\n---\n\nEarlier, happier run.\n")

        saved = save_provider_failure(
            ProviderError(_FAILURE_MESSAGE, tool_calls_made=0),
            "slice",
            _failure_slice_info(),
            model="glm53",
            cwd=str(tmp_path),
        )

        assert saved is not None
        assert "## Provider Failure" in saved.read_text()
        archived = list((reviews / "archive").glob("*.md"))
        assert len(archived) == 1
        assert "Earlier, happier run." in archived[0].read_text()

    def test_saved_failure_passes_the_verdict_gate(self, tmp_path: Path) -> None:
        """UNKNOWN is a real Verdict member, so Part 2's gate accepts it."""
        import asyncio

        from squadron.events import EventType
        from squadron.events.builtin.review_verdict_gate import ReviewVerdictGateAction
        from squadron.events.contexts import CommitContext

        (tmp_path / REVIEWS_DIR).mkdir(parents=True)
        saved = save_provider_failure(
            ProviderError(_FAILURE_MESSAGE),
            "slice",
            _failure_slice_info(),
            cwd=str(tmp_path),
        )
        assert saved is not None

        staged = str(saved.relative_to(tmp_path))
        result = asyncio.run(
            ReviewVerdictGateAction().execute(
                CommitContext(
                    event=EventType.COMMIT, cwd=str(tmp_path), params={}, staged_paths=(staged,)
                )
            )
        )

        assert result.success is True

    def test_part_suffix_lands_in_the_parts_own_slot(self, tmp_path: Path) -> None:
        """A split tasks review fails into the slot its success path writes.

        Without the suffix every failing part writes the unsuffixed slot — one
        no success path ever writes, and one where consecutive part failures
        overwrite each other.
        """
        (tmp_path / REVIEWS_DIR).mkdir(parents=True)

        first = save_provider_failure(
            ProviderError(_FAILURE_MESSAGE),
            "tasks",
            _failure_slice_info(),
            cwd=str(tmp_path),
            name_suffix="part-1",
        )
        second = save_provider_failure(
            ProviderError(_FAILURE_MESSAGE),
            "tasks",
            _failure_slice_info(),
            cwd=str(tmp_path),
            name_suffix="part-2",
        )

        assert first is not None and second is not None
        assert first.name == "917-review.tasks.review-artifact-integrity.part-1.md"
        assert second.name == "917-review.tasks.review-artifact-integrity.part-2.md"
        # Neither overwrote the other, so nothing was archived.
        assert not (tmp_path / REVIEWS_DIR / "archive").exists()

    def test_slice_less_save_names_the_file_from_the_fallback(self, tmp_path: Path) -> None:
        (tmp_path / REVIEWS_DIR).mkdir(parents=True)

        saved = save_provider_failure(
            ProviderError(_FAILURE_MESSAGE),
            "code",
            None,
            cwd=str(tmp_path),
            slice_name="nightly-audit",
            slice_index=3,
        )

        assert saved is not None
        assert saved.name == "3-review.code.nightly-audit.md"

    def test_slice_less_save_without_a_fallback_returns_none(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """No silent no-op: an unnameable artifact says so at WARNING."""
        caplog.set_level(logging.WARNING)
        (tmp_path / REVIEWS_DIR).mkdir(parents=True)

        saved = save_provider_failure(ProviderError(_FAILURE_MESSAGE), "code", None, cwd=str(tmp_path))

        assert saved is None
        assert any("provider-failure artifact" in r.getMessage() for r in caplog.records)


# ---------------------------------------------------------------------------
# Slice 917 Part 6: every artifact carries a run digest (#93)
# ---------------------------------------------------------------------------


class TestRunDigest:
    """The artifacts least likely to be questioned were the least auditable.

    A confident PASS kept nothing; only a degraded review embedded its raw
    response. So the runs most likely to be wrong were the ones with no
    evidence on disk.
    """

    @staticmethod
    def _pass_result(**overrides: object) -> ReviewResult:
        defaults: dict[str, object] = {
            "verdict": Verdict.PASS,
            "findings": [],
            "raw_output": "## Summary\nPASS\n",
            "template_name": "code",
            "input_files": {},
            "model": "glm53",
        }
        defaults.update(overrides)
        return ReviewResult(**defaults)  # type: ignore[arg-type]

    def test_clean_pass_carries_the_digest(self) -> None:
        markdown = format_review_markdown(self._pass_result(), "code")

        assert "### Run Digest" in markdown

    def test_counts_are_rendered_from_the_result_not_a_reparse(self) -> None:
        """Proves the formatter reports the parse that happened.

        The raw_output here contains no findings at all, so a formatter that
        re-parsed would report zeros. A second parse would drift from the
        first and describe a document nobody acted on.
        """
        result = self._pass_result(
            finding_scan=FindingScanCounts(total=35, in_fences=30, in_section=5, surviving=5)
        )

        markdown = format_review_markdown(result, "code")

        assert "whole response: 35" in markdown
        assert "inside fences: 30" in markdown
        assert "in findings section: 5" in markdown
        assert "surviving validation: 5" in markdown

    def test_hand_built_result_says_not_computed(self) -> None:
        """A result the parser did not produce has no counts to report."""
        markdown = format_review_markdown(self._pass_result(), "code")

        assert "whole response: not computed" in markdown
        assert "`## Findings` located: not computed" in markdown

    def test_tool_calls_distinguish_unused_from_never_offered(self) -> None:
        offered = format_review_markdown(
            self._pass_result(tools_given=["read_file"], tool_calls_made=0), "code"
        )
        never = format_review_markdown(self._pass_result(), "code")

        assert "Tool calls made: 0" in offered
        assert "Tool calls made: not offered" in never

    @pytest.mark.parametrize("verbosity_prompt", [None, "SYSTEM PROMPT TEXT"])
    def test_digest_is_present_regardless_of_verbosity(self, verbosity_prompt: str | None) -> None:
        result = self._pass_result(system_prompt=verbosity_prompt)

        markdown = format_review_markdown(result, "code")

        assert "### Run Digest" in markdown

    def test_degraded_raw_response_behavior_is_unchanged(self) -> None:
        result = self._pass_result(verdict=Verdict.UNKNOWN, raw_output="Prose, no structure.")

        markdown = format_review_markdown(result, "code")

        assert "### Run Digest" in markdown
        assert re.search(r"^### Raw Response\s*$", markdown, re.MULTILINE)


class TestStopReasonEvidenceInDigest:
    """Slice 918 (#92): the artifact alone must say why output was lost.

    The reproduction needed ``-vv`` and a live terminal to see the stop reason. Everything
    asserted here is readable from the saved artifact with neither.
    """

    @staticmethod
    def _result(**overrides: object) -> ReviewResult:
        defaults: dict[str, object] = {
            "verdict": Verdict.PASS,
            "findings": [],
            "raw_output": "## Summary\nPASS\n",
            "template_name": "code",
            "input_files": {},
            "model": "glm53",
        }
        defaults.update(overrides)
        return ReviewResult(**defaults)  # type: ignore[arg-type]

    def test_nonempty_response_parsing_to_nothing_shows_length_and_stop_reason(self) -> None:
        """The #92 signature: the model spoke, nothing parsed, and the reason is on disk.

        Response length alone cannot distinguish this from a healthy run; paired with a
        stop reason it names the cause without a re-run.
        """
        result = self._result(
            verdict=Verdict.UNKNOWN,
            raw_output="Let me start by reading the slice design so I can evaluate it",
            stop_reason="length",
            reasoning_chars=8192,
        )

        markdown = format_review_markdown(result, "slice")

        assert "- Response length: 61 chars" in markdown
        assert "- Stop reason: length" in markdown
        assert "- Reasoning characters: 8192" in markdown

    def test_all_tools_failing_shows_made_equal_to_failed(self) -> None:
        """The kimi27 shape, named at a glance by the adjacent made/failed pair."""
        markdown = format_review_markdown(
            self._result(tools_given=["read_file"], tool_calls_made=2, failed_tool_calls=2),
            "slice",
        )

        assert "- Tool calls made: 2" in markdown
        assert "- Tool calls failed: 2" in markdown

    def test_failed_line_immediately_follows_made_line(self) -> None:
        """Adjacency is the point: the pair is only readable at a glance if it is a pair."""
        markdown = format_review_markdown(
            self._result(tools_given=["read_file"], tool_calls_made=2, failed_tool_calls=2),
            "slice",
        )
        lines = markdown.splitlines()
        made = next(i for i, line in enumerate(lines) if line.startswith("- Tool calls made:"))

        assert lines[made + 1].startswith("- Tool calls failed:")

    def test_zero_failures_renders_as_zero_not_not_computed(self) -> None:
        """The ``or 0`` trap, inverted: 0 is a real answer and must render as one."""
        markdown = format_review_markdown(
            self._result(tools_given=["read_file"], tool_calls_made=3, failed_tool_calls=0),
            "slice",
        )

        assert "- Tool calls failed: 0" in markdown
        assert "- Tool calls failed: not computed" not in markdown

    def test_zero_reasoning_chars_renders_as_zero(self) -> None:
        """A non-reasoning model reporting 0 is not the same as nothing reporting."""
        markdown = format_review_markdown(self._result(reasoning_chars=0), "slice")

        assert "- Reasoning characters: 0" in markdown

    def test_sdk_path_renders_not_computed_never_a_fabricated_value(self) -> None:
        """Design D12: the SDK path stamps none of the three, and the digest says so."""
        markdown = format_review_markdown(self._result(), "slice")

        assert "- Stop reason: not computed" in markdown
        assert "- Reasoning characters: not computed" in markdown
        assert "- Tool calls failed: not computed" in markdown

    def test_real_newline_free_specimen_is_reported_as_newline_free(self) -> None:
        """The #96 shape, from the response that actually produced it.

        ``918-review.slice.review-grounding.md`` recorded a 3076-character reply with no
        line breaks at all, which collapsed ``## Summary`` and ``PASS`` into one token and
        made every heading unparseable. Fixtured verbatim so the indicator is proved
        against real input rather than a synthetic string.
        """
        specimen = (Path(__file__).parent / "fixtures" / "918-newline-free-response.txt").read_text()
        assert "\n" not in specimen, "fixture must stay newline-free to be this specimen"

        markdown = format_review_markdown(
            self._result(verdict=Verdict.UNKNOWN, raw_output=specimen), "slice"
        )

        assert "- Response is newline-free: yes" in markdown
        assert f"- Response length: {len(specimen)} chars" in markdown

    def test_ordinary_multiline_response_is_not_reported_as_newline_free(self) -> None:
        markdown = format_review_markdown(self._result(), "slice")

        assert "- Response is newline-free: no" in markdown

    def test_empty_response_is_not_reported_as_newline_free(self) -> None:
        """An empty response is the #92 shape, not the #96 one; the indicator must not
        conflate them just because it found no line breaks."""
        markdown = format_review_markdown(self._result(verdict=Verdict.UNKNOWN, raw_output=""), "slice")

        assert "- Response is newline-free: no" in markdown
        assert "- Response length: 0 chars" in markdown


class TestRunDigestEndToEnd:
    """Parsed, then formatted — the counts a real run would show."""

    def test_echoed_specimen_shows_a_gap_between_seen_and_kept(self) -> None:
        from squadron.review.parsers import parse_review_output

        response = (
            "## Summary\nCONCERNS\n\n"
            "### [PASS] Finding title\n"
            "Description of the finding.\n"
            "location: src/module.py:12\n\n"
            "## Findings\n\n"
            "### [CONCERN] A real problem\n"
            "Body.\n"
        )

        result = parse_review_output(response, "slice", {})
        markdown = format_review_markdown(result, "slice")

        assert result.finding_scan is not None
        assert result.finding_scan.total > result.finding_scan.surviving
        # The #91 signature, visible in the artifact without any raw text.
        assert "whole response: 2" in markdown
        assert "surviving validation: 1" in markdown

    def test_issue_92_prose_only_digest_reports_no_findings_section(self) -> None:
        """Part 4's done-when, asserted once end to end."""
        from squadron.review.parsers import parse_review_output

        prose = (
            "The task file sequencing is sound and every success criterion "
            "traces to at least one task. "
        ) * 18

        result = parse_review_output(prose, "tasks", {})
        markdown = format_review_markdown(result, "tasks")

        assert "`## Findings` located: no" in markdown
        assert "`## Summary` located: no" in markdown
        assert "surviving validation: 0" in markdown
