"""Canonical frontmatter values for all of squadron.

This module is the single definition of document status, docType, and
universal-field values used anywhere in squadron. Everything else — CLI
commands, review/pipeline writers, the validator — imports from here rather
than restating a value.

The upstream source of truth for process-document values is
``project-documents/ai-project-guide/file-naming-conventions.md`` (a git
submodule). ``tests/documents/test_schema_drift.py`` asserts this module still
agrees with it. The machine-artifact docTypes below are squadron-owned and
intentionally absent from that spec.
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

#: The five universal fields every process document's frontmatter must carry
#: (file-naming-conventions.md:20-27).
REQUIRED_UNIVERSAL_FIELDS: tuple[str, ...] = (
    "docType",
    "project",
    "dateCreated",
    "dateUpdated",
    "status",
)

#: Machine artifacts have no lifecycle, so no ``status``. Neither this tuple
#: nor the one above may require ``dateUpdated``: a validator reading one file
#: cannot know whether that file was ever edited after creation, so requiring
#: the field would be a check the tool cannot justify from the evidence in
#: front of it. Context Forge's schema requires it and backfills it from
#: ``dateCreated`` (frontmatterSchema.ts:224) — requiring it here too would
#: make this gate block commits on documents ``cf check --fix`` considers
#: valid. Do not "complete" this tuple by adding it.
MACHINE_ARTIFACT_REQUIRED_FIELDS: tuple[str, ...] = (
    "docType",
    "dateCreated",
)

#: Marker identifying IDE-generated frontmatter exempt from the universal
#: schema (file-naming-conventions.md:43).
CONTEXT_FORGE_MANAGED_MARKER = "context-forge:managed"
