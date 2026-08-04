"""Mechanical frontmatter validation.

Pure: takes paths, returns ``list[Violation]``. No printing, no ``sys.exit``.
That keeps this testable without a CLI runner and callable later from
``sq doctor`` or an MCP tool. The CLI command (``cli/commands/validate.py``)
owns formatting and exit codes.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import cast

import yaml

from squadron.documents.frontmatter import split_document
from squadron.documents.schema import (
    CONTEXT_FORGE_MANAGED_MARKER,
    MACHINE_ARTIFACT_DOC_TYPES,
    MACHINE_ARTIFACT_REQUIRED_FIELDS,
    REQUIRED_UNIVERSAL_FIELDS,
    STATUS_ALIASES,
    DocType,
    DocumentStatus,
)

_DATE_FIELDS = ("dateCreated", "dateUpdated")
_DATE_PATTERN = re.compile(r"^\d{8}$")
_MARKER_SCAN_BYTES = 2048


class ViolationCode(StrEnum):
    """One code per mechanical check; each has exactly one fix."""

    FM001 = "FM001"  # no frontmatter block
    FM002 = "FM002"  # block present, invalid YAML
    FM003 = "FM003"  # parses, not a mapping
    FM004 = "FM004"  # missing universal required field
    FM005 = "FM005"  # invalid status
    FM006 = "FM006"  # invalid docType
    FM007 = "FM007"  # malformed date
    FM008 = "FM008"  # not UTF-8 decodable


@dataclass(frozen=True)
class Violation:
    """One mechanical frontmatter defect in one document."""

    path: Path
    line: int
    code: ViolationCode
    key: str | None
    actual: str | None
    accepted: tuple[str, ...]
    detail: str | None


class DocumentRootError(Exception):
    """Raised when a configured or named path does not exist.

    Not ``SystemExit`` — the CLI layer maps this to exit 2, an invocation
    error distinct from a document-content violation (exit 1).
    """


def _is_real_date(value: str) -> bool:
    if not _DATE_PATTERN.match(value):
        return False
    try:
        date(int(value[0:4]), int(value[4:6]), int(value[6:8]))
    except ValueError:
        return False
    return True


def _find_key_line(raw_block: str, key: str, *, block_start_line: int) -> int:
    """Line of a top-level ``key:`` inside the raw block, or the fence line.

    Scans rather than trusting YAML's own position info, since a key that
    fails to parse (FM002) has no such info to trust.
    """
    for offset, line in enumerate(raw_block.splitlines()):
        if line.startswith(f"{key}:"):
            return block_start_line + offset
    return block_start_line


def _yaml_error_line(exc: yaml.YAMLError, *, block_start_line: int) -> int:
    mark = getattr(exc, "problem_mark", None)
    if mark is None:
        return block_start_line
    return block_start_line + mark.line


def validate_document(path: Path) -> list[Violation]:
    """Validate one document's frontmatter, returning every violation found.

    A document that fails one check is still checked against the rest —
    a caller fixing one problem should not have to re-run to discover another.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        return [
            Violation(
                path=path,
                line=1,
                code=ViolationCode.FM008,
                key=None,
                actual=None,
                accepted=(),
                detail=str(exc),
            )
        ]

    split = split_document(text)
    if split is None:
        return [
            Violation(
                path=path,
                line=1,
                code=ViolationCode.FM001,
                key=None,
                actual=None,
                accepted=(),
                detail=None,
            )
        ]

    leading, raw_block, _body = split
    # The block's raw text starts one line after the opening "---" fence, on
    # the line following whatever leading blank/BOM prefix preceded it.
    block_start_line = leading.count("\n") + 2

    try:
        loaded = yaml.safe_load(raw_block)
    except yaml.YAMLError as exc:
        return [
            Violation(
                path=path,
                line=_yaml_error_line(exc, block_start_line=block_start_line),
                code=ViolationCode.FM002,
                key=None,
                actual=None,
                accepted=(),
                detail=str(exc),
            )
        ]

    if not isinstance(loaded, dict):
        return [
            Violation(
                path=path,
                line=block_start_line,
                code=ViolationCode.FM003,
                key=None,
                actual=None,
                accepted=(),
                detail=None,
            )
        ]

    data: dict[str, object] = {
        str(key): value for key, value in cast("dict[object, object]", loaded).items()
    }
    violations: list[Violation] = []

    doc_type = data.get("docType")
    valid_doc_types = {member.value for member in DocType} | MACHINE_ARTIFACT_DOC_TYPES
    if doc_type not in valid_doc_types:
        violations.append(
            Violation(
                path=path,
                line=_find_key_line(raw_block, "docType", block_start_line=block_start_line),
                code=ViolationCode.FM006,
                key="docType",
                actual=str(doc_type) if doc_type is not None else None,
                accepted=tuple(sorted(valid_doc_types)),
                detail=None,
            )
        )

    is_machine_artifact = doc_type in MACHINE_ARTIFACT_DOC_TYPES
    required_fields = (
        MACHINE_ARTIFACT_REQUIRED_FIELDS if is_machine_artifact else REQUIRED_UNIVERSAL_FIELDS
    )
    for field_name in required_fields:
        if field_name not in data:
            violations.append(
                Violation(
                    path=path,
                    line=block_start_line,
                    code=ViolationCode.FM004,
                    key=field_name,
                    actual=None,
                    accepted=(),
                    detail=None,
                )
            )

    if not is_machine_artifact and "status" in data:
        status_value = data["status"]
        valid_statuses = {member.value for member in DocumentStatus} | set(STATUS_ALIASES)
        if str(status_value) not in valid_statuses:
            violations.append(
                Violation(
                    path=path,
                    line=_find_key_line(raw_block, "status", block_start_line=block_start_line),
                    code=ViolationCode.FM005,
                    key="status",
                    actual=str(status_value),
                    accepted=tuple(member.value for member in DocumentStatus),
                    detail=None,
                )
            )

    for date_field in _DATE_FIELDS:
        if date_field not in data:
            continue
        date_value = data[date_field]
        # YAML parses an unquoted `dateCreated: 20260803` as an int — the norm
        # in this corpus (ResolutionRecord.date_created is itself typed int).
        # A quoted string is also accepted; anything else cannot be a date.
        is_int_not_bool = isinstance(date_value, int) and not isinstance(date_value, bool)
        as_text = str(date_value) if is_int_not_bool or isinstance(date_value, str) else None
        if as_text is None or not _is_real_date(as_text):
            violations.append(
                Violation(
                    path=path,
                    line=_find_key_line(raw_block, date_field, block_start_line=block_start_line),
                    code=ViolationCode.FM007,
                    key=date_field,
                    actual=str(date_value),
                    accepted=("YYYYMMDD",),
                    detail=None,
                )
            )

    return sorted(violations, key=lambda v: v.line)


def _is_managed(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            head = f.read(_MARKER_SCAN_BYTES)
    except OSError:
        return False
    return CONTEXT_FORGE_MANAGED_MARKER.encode("utf-8") in head


def _collect_root_paths(root: Path) -> list[Path]:
    return sorted(root.rglob("*.md"))


def _resolve_under_root(path: Path, *, root: Path) -> Path | None:
    resolved_root = root.resolve()
    resolved_path = path.resolve()
    if resolved_path.suffix != ".md":
        return None
    if resolved_root not in resolved_path.parents and resolved_path != resolved_root:
        return None
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError:
        return None
    return resolved_path


def select_document_paths(paths: Sequence[Path] | None, *, root: Path) -> list[Path]:
    """Resolve *paths* (or the whole root) to the documents that will be checked.

    Shared by ``validate_paths`` and the CLI's summary line, so "how many
    documents did this run check" is answered identically in both places.

    Raises:
        DocumentRootError: *root* does not exist, or a named path does not
            exist.
    """
    if not root.is_dir():
        raise DocumentRootError(f"Document root does not exist: {root}")

    if paths is None:
        candidates = _collect_root_paths(root)
    else:
        candidates: list[Path] = []
        for given in paths:
            if not given.exists():
                raise DocumentRootError(f"Path does not exist: {given}")
            resolved = _resolve_under_root(given, root=root)
            if resolved is not None:
                candidates.append(resolved)

    return [candidate for candidate in candidates if not _is_managed(candidate)]


def validate_paths(paths: Sequence[Path] | None, *, root: Path) -> list[Violation]:
    """Validate documents under *root*.

    With ``paths=None``, walks *root* for every ``*.md`` file. With paths
    given, validates only those that are ``.md`` **and** resolve under
    *root* — others are silently skipped, so a caller (the pre-commit hook)
    can pass the whole staged file list without knowing which files are
    process documents.

    Raises:
        DocumentRootError: *root* does not exist, or a named path does not
            exist.
    """
    candidates = select_document_paths(paths, root=root)

    violations: list[Violation] = []
    for candidate in candidates:
        violations.extend(validate_document(candidate))

    return sorted(violations, key=lambda v: (v.path, v.line))
