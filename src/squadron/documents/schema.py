"""Canonical frontmatter values squadron writes.

This module is the single definition of the document status and docType
values squadron *emits*. The review/devlog/evidence writers import from here
rather than restating a value.

Context Forge owns the frontmatter schema and validates it (D10 — validation
is ``cf validate frontmatter``, wired into the pre-commit hook, not squadron
code). ``tests/documents/test_schema_drift.py`` asserts cf still accepts every
value defined here.
"""

from __future__ import annotations

from enum import StrEnum


class DocumentStatus(StrEnum):
    """The five canonical lifecycle values a process document's status may hold."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    DEFERRED = "deferred"
    DEPRECATED = "deprecated"


#: Accepted on read only. Nothing in squadron emits an alias — new documents
#: use the canonical spelling in ``DocumentStatus``.
STATUS_ALIASES: dict[str, DocumentStatus] = {
    "completed": DocumentStatus.COMPLETE,
}


class DocType(StrEnum):
    """The fifteen process-document ``docType`` values in the spec."""

    GUIDE = "guide"
    REFERENCE = "reference"
    CONCEPT = "concept"
    INITIATIVE_PLAN = "initiative-plan"
    ARCHITECTURE = "architecture"
    SLICE_PLAN = "slice-plan"
    SLICE_DESIGN = "slice-design"
    SLICE = "slice"
    TASKS = "tasks"
    ANALYSIS = "analysis"
    REVIEW = "review"
    NOTES = "notes"
    TEMPLATE = "template"
    INTRO_GUIDE = "intro-guide"
    MIGRATION = "migration"


#: docType values squadron itself writes into the document tree that are not
#: part of the spec above. These have no lifecycle and carry no ``status``.
RESOLUTION_DOC_TYPE = "review-resolution"
GATE_EVIDENCE_DOC_TYPE = "gate-evidence"
DEVLOG_DOC_TYPE = "devlog"

MACHINE_ARTIFACT_DOC_TYPES: frozenset[str] = frozenset(
    {RESOLUTION_DOC_TYPE, GATE_EVIDENCE_DOC_TYPE, DEVLOG_DOC_TYPE}
)
