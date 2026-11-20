"""Blob stamps for the reviewed document and its parent (#374, part 1)."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import pytest

from squadron.review.document_stamp import (
    BlobStamp,
    DocumentBlobs,
    document_blob_lines,
    resolve_blob_stamp,
    resolve_document_blobs,
)
from squadron.review.models import ReviewResult, Verdict
from squadron.review.persistence import format_review_markdown
from tests.conftest import run_test_git


def _commit_file(repo: Path, name: str, text: str) -> Path:
    path = repo / name
    path.write_text(text)
    run_test_git(repo, "add", name)
    run_test_git(repo, "commit", "-q", "-m", f"add {name}")
    return path


def _head_blob(repo: Path, name: str) -> str:
    return run_test_git(repo, "rev-parse", f"HEAD:{name}").strip()


class TestResolveBlobStamp:
    def test_committed_unchanged_file_is_current(self, temp_git_repo: Path) -> None:
        path = _commit_file(temp_git_repo, "design.md", "# Design\n")

        stamp = resolve_blob_stamp(path)

        assert stamp == BlobStamp(blob=_head_blob(temp_git_repo, "design.md"), current=True)

    def test_edited_file_is_not_current(self, temp_git_repo: Path) -> None:
        path = _commit_file(temp_git_repo, "design.md", "# Design\n")
        head_blob = _head_blob(temp_git_repo, "design.md")
        path.write_text("# Design, edited after commit\n")

        stamp = resolve_blob_stamp(path)

        assert stamp is not None
        assert stamp.current is False
        assert stamp.blob != head_blob

    def test_uncommitted_new_file_is_not_current(self, temp_git_repo: Path) -> None:
        path = temp_git_repo / "new.md"
        path.write_text("# Not committed yet\n")

        stamp = resolve_blob_stamp(path)

        assert stamp is not None
        assert stamp.current is False

    def test_missing_file_is_unresolved_with_warning(
        self, temp_git_repo: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING):
            stamp = resolve_blob_stamp(temp_git_repo / "absent.md")

        assert stamp is None
        assert "is not a file" in caplog.text

    def test_file_outside_a_repository_is_unresolved_with_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        loose = tmp_path / "loose.md"
        loose.write_text("# Loose\n")

        with caplog.at_level(logging.WARNING):
            stamp = resolve_blob_stamp(loose)

        assert stamp is None
        assert "not in a git repository" in caplog.text


class TestResolveDocumentBlobs:
    def test_no_document_resolves_to_none(self) -> None:
        assert resolve_document_blobs(None) is None

    def test_parent_named_in_frontmatter_is_stamped(self, temp_git_repo: Path) -> None:
        arch = _commit_file(temp_git_repo, "arch.md", "# Architecture\n")
        design = _commit_file(
            temp_git_repo,
            "design.md",
            f"---\ndocType: slice\nparent: {arch}\n---\n# Design\n",
        )

        blobs = resolve_document_blobs(design)

        assert blobs is not None
        assert blobs.document is not None and blobs.document.current is True
        assert blobs.parent == BlobStamp(blob=_head_blob(temp_git_repo, "arch.md"), current=True)

    def test_document_without_parent_has_no_parent_stamp(self, temp_git_repo: Path) -> None:
        design = _commit_file(temp_git_repo, "design.md", "---\ndocType: slice\n---\n# Design\n")

        blobs = resolve_document_blobs(design)

        assert blobs is not None
        assert blobs.document is not None
        assert blobs.parent is None


class TestDocumentBlobLines:
    def test_renders_document_and_parent_keys(self) -> None:
        blobs = DocumentBlobs(
            document=BlobStamp(blob="a" * 40, current=False),
            parent=BlobStamp(blob="b" * 40, current=True),
        )

        assert document_blob_lines(blobs) == [
            f"reviewedBlob: {'a' * 40}",
            "reviewedBlobCurrent: false",
            f"parentBlob: {'b' * 40}",
            "parentBlobCurrent: true",
        ]

    def test_unresolved_stamps_write_no_keys(self) -> None:
        assert document_blob_lines(DocumentBlobs(document=None, parent=None)) == []


def _review_markdown(source_document: str) -> str:
    result = ReviewResult(
        verdict=Verdict.PASS,
        findings=[],
        raw_output="",
        template_name="design",
        input_files={"input": source_document},
        timestamp=datetime(2026, 11, 19, 12, 0, 0),
        model="claude-opus-4-5",
    )
    return format_review_markdown(result, "slice", source_document=source_document)


class TestReviewFrontmatter:
    def test_review_of_committed_document_carries_blob_keys(self, temp_git_repo: Path) -> None:
        design = _commit_file(temp_git_repo, "design.md", "# Design\n")

        md = _review_markdown(str(design))

        assert f"reviewedBlob: {_head_blob(temp_git_repo, 'design.md')}" in md
        assert "reviewedBlobCurrent: true" in md

    def test_review_outside_a_repository_omits_blob_keys(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        loose = tmp_path / "loose.md"
        loose.write_text("# Loose\n")

        with caplog.at_level(logging.WARNING):
            md = _review_markdown(str(loose))

        assert "reviewedBlob" not in md
        assert "not in a git repository" in caplog.text
