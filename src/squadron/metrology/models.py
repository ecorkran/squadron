"""Pydantic records at the metrology file boundary.

These are the shapes persisted to and read from the metrology store. Value
objects that participate in identity (``ProjectId``, ``JudgeResultRef``,
``JudgeConfigId``) live here so both ``identity.py`` (which derives them) and
``store.py`` (which persists them) depend on one definition.

This module is grown across the slice's tasks: T2 lands ``ProjectId``; T4
adds the reference/config-id models; T6 adds ``SampleVerdict`` and the
``MetrologyRecord`` envelope.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel

from squadron.review.models import Verdict

#: Record types the store envelope may carry. ``sample`` is written by this
#: slice; ``audit_finding`` is reserved for 323's tech-debt-audit oracle so it
#: can extend the store behind the same discriminator without a migration.
RECORD_TYPE_SAMPLE = "sample"
RECORD_TYPE_AUDIT_FINDING = "audit_finding"


class ProjectIdSource(StrEnum):
    """Where a ``ProjectId``'s canonical value came from.

    ``remote`` — derived from the git remote URL.
    ``recorded`` — read from ``.squadron.toml`` (``metrology.project_id``).
    """

    REMOTE = "remote"
    RECORDED = "recorded"


class ProjectId(BaseModel):
    """A stable, explicit project identity — never a filesystem path.

    ``value`` is the canonical identity string (git-remote-derived or a
    recorded id). ``source`` marks which it is, so downstream slices can
    reason about identity provenance.
    """

    value: str
    source: ProjectIdSource


class JudgeResultRef(BaseModel):
    """A content-addressed pointer to one persisted 300 judge result.

    300 results carry no id and are overwritten on re-run, so the reference
    is ``(project_id, relative_review_path, content_hash)`` where
    ``content_hash`` is a SHA-256 over a canonical projection of the judge
    fields — stable for a given result, distinct after a re-run overwrites
    the file. This is what makes a sample attach unambiguously to one result.
    """

    project_id: str
    relative_review_path: str
    content_hash: str


class JudgeConfigId(BaseModel):
    """The judge-configuration identity a sample was graded under.

    ``(template_name, model, template_content_hash)``. The template-content
    hash is computed at capture time from the resolved template; 322 decides
    whether it or a coordinated 300 write-path field becomes the
    comparability key. This slice records it.
    """

    template_name: str
    model: str
    template_content_hash: str | None = None


class SampleVerdict(BaseModel):
    """One human calibration verdict graded blind against a judge result."""

    sample_id: str
    project_id: ProjectId
    result_ref: JudgeResultRef
    judge_config: JudgeConfigId
    human_verdict: Verdict
    human_note: str | None = None
    #: Artifact grain (e.g. "slice" vs "tasks") — recorded when resolvable so
    #: 321 can report agreement per artifact level without a schema change.
    artifact_level: str | None = None
    captured_at: datetime
    #: Always True for this surface. Recorded so that if a non-blind capture
    #: path is ever added, anchored verdicts can never masquerade as blind
    #: agreement data and 321 can exclude them.
    blind: bool = True


class MetrologyRecord(BaseModel):
    """The on-disk envelope: one JSON file per record in the store.

    ``record_type`` discriminates the payload. This slice writes only
    ``"sample"`` records (``sample`` set, other payloads absent); the
    envelope reserves room for 323's ``"audit_finding"`` behind the same
    discriminator, so a second record type needs no store migration.
    """

    schema_version: int
    record_type: str = RECORD_TYPE_SAMPLE
    sample: SampleVerdict | None = None
