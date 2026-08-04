"""Tests for squadron.documents.frontmatter."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from squadron.documents.frontmatter import (
    FrontmatterError,
    read_frontmatter,
    render_frontmatter_block,
    update_frontmatter,
)

_REAL_SLICE_DOC = (
    Path(__file__).parents[2]
    / "project-documents"
    / "user"
    / "slices"
    / "911-slice.loop-iteration-versioning-and-review-evidence.md"
)


# ---------------------------------------------------------------------------
# read_frontmatter
# ---------------------------------------------------------------------------


def test_read_frontmatter_normal_block(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text("---\nkey: value\nother: 1\n---\nbody text\n", encoding="utf-8")

    result = read_frontmatter(doc)

    assert result == {"key": "value", "other": 1}


def test_read_frontmatter_bom_prefixed(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text("﻿---\nkey: value\n---\nbody\n", encoding="utf-8")

    result = read_frontmatter(doc)

    assert result == {"key": "value"}


def test_read_frontmatter_leading_blank_lines(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text("\n\n---\nkey: value\n---\nbody\n", encoding="utf-8")

    result = read_frontmatter(doc)

    assert result == {"key": "value"}


def test_read_frontmatter_no_block(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text("# Just a heading\n\nSome text.\n", encoding="utf-8")

    assert read_frontmatter(doc) is None


def test_read_frontmatter_scalar_not_mapping(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text("---\njust a scalar string\n---\nbody\n", encoding="utf-8")

    assert read_frontmatter(doc) is None


# ---------------------------------------------------------------------------
# update_frontmatter
# ---------------------------------------------------------------------------


def test_update_frontmatter_adds_new_key(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text("---\nexisting: 1\n---\nbody\n", encoding="utf-8")

    update_frontmatter(doc, {"revision_number": 1}, today="20260803")

    result = read_frontmatter(doc)
    assert result == {"existing": 1, "revision_number": 1, "dateUpdated": "20260803"}


def test_update_frontmatter_updates_existing_key(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text("---\nrevision_number: 1\nother: x\n---\nbody\n", encoding="utf-8")

    update_frontmatter(doc, {"revision_number": 2}, today="20260803")

    result = read_frontmatter(doc)
    assert result == {"revision_number": 2, "other": "x", "dateUpdated": "20260803"}


def test_update_frontmatter_preserves_order_of_untouched_keys(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text("---\na: 1\nb: 2\nc: 3\n---\nbody\n", encoding="utf-8")

    update_frontmatter(doc, {"b": 20}, today="20260803")

    text = doc.read_text(encoding="utf-8")
    fence_block = text.split("---", 2)[1]
    keys_in_order = [line.split(":")[0] for line in fence_block.strip().splitlines()]
    assert keys_in_order == ["a", "b", "c", "dateUpdated"]


def test_update_frontmatter_byte_preserves_real_document_body(tmp_path: Path) -> None:
    assert _REAL_SLICE_DOC.is_file(), f"fixture missing: {_REAL_SLICE_DOC}"
    doc = tmp_path / _REAL_SLICE_DOC.name
    shutil.copy(_REAL_SLICE_DOC, doc)

    original_text = doc.read_text(encoding="utf-8")
    original_body = original_text.split("---", 2)[2]

    update_frontmatter(doc, {"revision_number": 1}, today="20260803")

    new_text = doc.read_text(encoding="utf-8")
    new_body = new_text.split("---", 2)[2]
    assert new_body == original_body

    updated = read_frontmatter(doc)
    assert updated is not None
    assert updated["revision_number"] == 1
    # Original keys are untouched.
    assert updated["docType"] == "slice-design"


def test_update_frontmatter_no_block_raises(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text("# no frontmatter here\n", encoding="utf-8")

    with pytest.raises(FrontmatterError):
        update_frontmatter(doc, {"revision_number": 1}, today="20260803")


def test_update_frontmatter_unclosed_block_raises(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text("---\nkey: value\nno closing fence\n", encoding="utf-8")

    with pytest.raises(FrontmatterError):
        update_frontmatter(doc, {"revision_number": 1}, today="20260803")


def test_update_frontmatter_non_mapping_raises(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text("---\njust a scalar string\n---\nbody\n", encoding="utf-8")

    with pytest.raises(FrontmatterError):
        update_frontmatter(doc, {"revision_number": 1}, today="20260803")


def test_update_frontmatter_malformed_yaml_raises(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text("---\nkey: [unclosed\n---\nbody\n", encoding="utf-8")

    with pytest.raises(FrontmatterError):
        update_frontmatter(doc, {"revision_number": 1}, today="20260803")


def test_update_frontmatter_output_is_valid_yaml(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text("---\na: 1\n---\nbody\n", encoding="utf-8")

    update_frontmatter(doc, {"b": 2}, today="20260803")

    text = doc.read_text(encoding="utf-8")
    fence_block = text.split("---", 2)[1]
    assert yaml.safe_load(fence_block) == {"a": 1, "b": 2, "dateUpdated": "20260803"}


# ---------------------------------------------------------------------------
# Status validation hardening (slice 172, D8/T13)
# ---------------------------------------------------------------------------


def test_update_frontmatter_invalid_status_raises(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text("---\ndocType: notes\nstatus: not_started\n---\nbody\n", encoding="utf-8")

    with pytest.raises(FrontmatterError, match="not_started|in_progress|complete|deferred|deprecated"):
        update_frontmatter(doc, {"status": "draft"}, today="20260803")


def test_update_frontmatter_valid_status_succeeds_and_preserves_body(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text("---\ndocType: notes\nstatus: not_started\n---\nbody text\n", encoding="utf-8")

    update_frontmatter(doc, {"status": "complete"}, today="20260803")

    text = doc.read_text(encoding="utf-8")
    fence_block = text.split("---", 2)[1]
    assert yaml.safe_load(fence_block)["status"] == "complete"
    assert text.endswith("body text\n")


def test_render_frontmatter_block_nested_finding_status_does_not_raise() -> None:
    data: dict[str, object] = {
        "docType": "gate-evidence",
        "findingStatuses": [{"id": "F001", "status": "addressed"}],
    }

    rendered = render_frontmatter_block(data)

    assert "findingStatuses" in rendered


def test_render_frontmatter_block_no_status_key_does_not_raise() -> None:
    data: dict[str, object] = {"docType": "gate-evidence", "layer": "project"}

    rendered = render_frontmatter_block(data)

    assert "docType: gate-evidence" in rendered


# ---------------------------------------------------------------------------
# dateUpdated stamping (slice 172, D8/T23)
# ---------------------------------------------------------------------------


def test_update_frontmatter_stamps_dateupdated_and_leaves_datecreated(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text("---\ndateCreated: 20260801\ndateUpdated: 20260801\n---\nbody\n", encoding="utf-8")

    update_frontmatter(doc, {"revision_number": 1}, today="20260804")

    result = read_frontmatter(doc)
    assert result is not None
    assert result["dateUpdated"] == "20260804"
    assert result["dateCreated"] == 20260801


def test_update_frontmatter_caller_supplied_dateupdated_wins(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text("---\ndateUpdated: 20260801\n---\nbody\n", encoding="utf-8")

    update_frontmatter(doc, {"dateUpdated": "20260802"}, today="20260804")

    result = read_frontmatter(doc)
    assert result is not None
    assert result["dateUpdated"] == "20260802"


def test_update_frontmatter_stamps_dateupdated_even_without_datecreated(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text("---\ndocType: gate-evidence\n---\nbody\n", encoding="utf-8")

    update_frontmatter(doc, {"revision_number": 1}, today="20260804")

    result = read_frontmatter(doc)
    assert result is not None
    assert result["dateUpdated"] == "20260804"
    assert "dateCreated" not in result


def test_update_frontmatter_stamp_preserves_body_byte_for_byte(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text("---\ndateUpdated: 20260801\n---\n\nexact body text\n", encoding="utf-8")

    update_frontmatter(doc, {"revision_number": 1}, today="20260804")

    text = doc.read_text(encoding="utf-8")
    body = text.split("---", 2)[2]
    assert body == "\n\nexact body text\n"
