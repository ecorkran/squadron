"""Fails when file-naming-conventions.md and the schema enums disagree.

Deliberately fails rather than skips when the submodule is absent — a skipped
drift test is a silent fallback, and drift is the exact risk that left slice
171's frontmatter consumer designing against a schema nobody re-checked.
"""

from __future__ import annotations

import re
from pathlib import Path

from squadron.documents.schema import MACHINE_ARTIFACT_DOC_TYPES, DocType, DocumentStatus

_SPEC_PATH = Path("project-documents/ai-project-guide/file-naming-conventions.md")

_STATUS_SECTION_RE = re.compile(r"###\s*Valid Status Values\s*\n(.*?)(?=\n##|\Z)", re.DOTALL)
_STATUS_BULLET_RE = re.compile(r"^-\s*`([a-z_]+)`", re.MULTILINE)
_DOCTYPE_LINE_RE = re.compile(r"Valid `docType` values:\s*(.+)$")
_BACKTICK_TOKEN_RE = re.compile(r"`([a-z-]+)`")


def _read_spec() -> str:
    if not _SPEC_PATH.is_file():
        raise AssertionError(
            f"{_SPEC_PATH} not found — run 'git submodule update --init' "
            "to fetch the ai-project-guide submodule before running this test"
        )
    return _SPEC_PATH.read_text(encoding="utf-8")


def _parse_status_values(spec_text: str) -> set[str]:
    section_match = _STATUS_SECTION_RE.search(spec_text)
    if not section_match:
        raise AssertionError("Could not find a '### Valid Status Values' section in the spec")
    return set(_STATUS_BULLET_RE.findall(section_match.group(1)))


def _parse_doctype_values(spec_text: str) -> set[str]:
    for line in spec_text.splitlines():
        match = _DOCTYPE_LINE_RE.search(line)
        if match:
            return set(_BACKTICK_TOKEN_RE.findall(match.group(1)))
    raise AssertionError("Could not find a 'Valid `docType` values:' line in the spec")


def test_status_enum_matches_spec() -> None:
    spec_text = _read_spec()
    spec_values = _parse_status_values(spec_text)
    enum_values = {member.value for member in DocumentStatus}
    assert spec_values == enum_values


def test_doctype_enum_matches_spec() -> None:
    spec_text = _read_spec()
    spec_values = _parse_doctype_values(spec_text)
    enum_values = {member.value for member in DocType}
    assert spec_values == enum_values


def test_machine_artifact_types_are_not_in_spec() -> None:
    spec_text = _read_spec()
    spec_doctypes = _parse_doctype_values(spec_text)
    assert not (MACHINE_ARTIFACT_DOC_TYPES & spec_doctypes)
