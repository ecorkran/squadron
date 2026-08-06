"""Tests for squadron.documents.validate.validate_paths."""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.documents.schema import CONTEXT_FORGE_MANAGED_MARKER
from squadron.documents.validate import DocumentRootError, ViolationCode, validate_paths

_VALID_DOC = (
    "---\n"
    "docType: notes\n"
    "project: squadron\n"
    "dateCreated: 20260803\n"
    "dateUpdated: 20260803\n"
    "status: not_started\n"
    "---\n\nbody\n"
)

_INVALID_DOC = (
    "---\n"
    "docType: notes\n"
    "project: squadron\n"
    "dateCreated: 20260803\n"
    "dateUpdated: 20260803\n"
    "status: draft\n"
    "---\n\nbody\n"
)


@pytest.fixture
def doc_root(tmp_path: Path) -> Path:
    root = tmp_path / "project-documents" / "user"
    root.mkdir(parents=True)
    return root


def test_files_outside_root_yield_zero_violations(tmp_path: Path, doc_root: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("# no frontmatter here\n", encoding="utf-8")
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("# also no frontmatter\n", encoding="utf-8")
    quickstart = tmp_path / "docs" / "QUICKSTART.md"
    quickstart.parent.mkdir(parents=True)
    quickstart.write_text("# quickstart\n", encoding="utf-8")

    violations = validate_paths([readme, claude_md, quickstart], root=doc_root)

    assert violations == []


def test_mixed_list_yields_only_the_in_root_violation(tmp_path: Path, doc_root: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("# no frontmatter\n", encoding="utf-8")
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("# no frontmatter\n", encoding="utf-8")
    quickstart = tmp_path / "docs" / "QUICKSTART.md"
    quickstart.parent.mkdir(parents=True)
    quickstart.write_text("# quickstart\n", encoding="utf-8")
    bad_doc = doc_root / "notes" / "bad.md"
    bad_doc.parent.mkdir(parents=True)
    bad_doc.write_text(_INVALID_DOC, encoding="utf-8")

    violations = validate_paths([readme, claude_md, quickstart, bad_doc], root=doc_root)

    assert len(violations) == 1
    assert violations[0].code == ViolationCode.FM005
    assert violations[0].path == bad_doc


def test_context_forge_managed_marker_is_skipped(doc_root: Path) -> None:
    managed = doc_root / "notes" / "managed.md"
    managed.parent.mkdir(parents=True)
    managed.write_text(f"[//]: # ({CONTEXT_FORGE_MANAGED_MARKER})\n\n{_INVALID_DOC}", encoding="utf-8")

    violations = validate_paths([managed], root=doc_root)

    assert violations == []


def test_non_markdown_file_in_root_is_skipped(doc_root: Path) -> None:
    not_markdown = doc_root / "notes" / "data.json"
    not_markdown.parent.mkdir(parents=True)
    not_markdown.write_text("{not even valid frontmatter}", encoding="utf-8")

    violations = validate_paths([not_markdown], root=doc_root)

    assert violations == []


def test_nonexistent_root_raises(tmp_path: Path) -> None:
    missing_root = tmp_path / "does-not-exist"

    with pytest.raises(DocumentRootError):
        validate_paths(None, root=missing_root)


def test_nonexistent_named_path_raises(doc_root: Path) -> None:
    missing = doc_root / "notes" / "ghost.md"

    with pytest.raises(DocumentRootError):
        validate_paths([missing], root=doc_root)


def test_none_paths_walks_root(doc_root: Path) -> None:
    good = doc_root / "notes" / "good.md"
    good.parent.mkdir(parents=True)
    good.write_text(_VALID_DOC, encoding="utf-8")
    bad = doc_root / "notes" / "bad.md"
    bad.write_text(_INVALID_DOC, encoding="utf-8")

    violations = validate_paths(None, root=doc_root)

    assert len(violations) == 1
    assert violations[0].path == bad


def test_violations_sorted_by_path_then_line(doc_root: Path) -> None:
    a = doc_root / "a.md"
    a.write_text(_INVALID_DOC, encoding="utf-8")
    z = doc_root / "z.md"
    z.write_text(_INVALID_DOC, encoding="utf-8")

    violations = validate_paths(None, root=doc_root)

    assert [v.path for v in violations] == sorted(v.path for v in violations)
