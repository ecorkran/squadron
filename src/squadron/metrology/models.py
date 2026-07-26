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

from squadron.metrology.levels import ArtifactLevel
from squadron.review.models import Verdict

#: Record types the store envelope may carry. ``sample`` is written by 320;
#: ``graduated_config`` is written by 322's graduation registry;
#: ``audit_finding`` and ``audit_noise_floor`` are written by 323's
#: tech-debt-audit oracle, which extends the store behind the same
#: discriminator without a migration.
RECORD_TYPE_SAMPLE = "sample"
RECORD_TYPE_GRADUATED_CONFIG = "graduated_config"
RECORD_TYPE_AUDIT_FINDING = "audit_finding"
RECORD_TYPE_AUDIT_NOISE_FLOOR = "audit_noise_floor"


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


class EvidenceSnapshot(BaseModel):
    """The evidence a calibration direction was classified from.

    Lives here (not ``calibration_models.py``) because ``GraduatedConfig``
    — an envelope payload — embeds it; keeping both payload types in one
    module avoids a circular import between the envelope and 322's output
    shapes.
    """

    n: int
    match_rate: float
    floor_applied: int
    below_floor: bool


class GraduatedConfig(BaseModel):
    """A persisted record of an operator's graduation decision (322).

    Carries the **full** ``JudgeConfigId`` (template_name + model +
    template_content_hash), not just the looser ``(template_name, model)``
    pair — this is what makes a graduation version-scoped: it survives a
    threshold-only edit (which does not change the hash) but lapses on a
    prompt/model edit (which does).
    """

    judge_config: JudgeConfigId
    artifact_level: ArtifactLevel
    evidence: EvidenceSnapshot
    graduated_at: datetime


class AuditCategory(StrEnum):
    """The closed issue-class vocabulary audit findings normalize into (323).

    Nine values mirror the audit skill's nine prose dimensions; ``OTHER`` is
    the tenth and is **load-bearing, not a dumping ground**. A finding whose
    category the model invents outside this vocabulary normalizes to
    ``OTHER`` with its original string retained on
    ``AuditFinding.raw_category`` — nothing is discarded. A rising ``other``
    share is evidence the vocabulary does not fit a codebase, which the
    baseline report surfaces rather than hides.

    The skill file enumerates these same ten values. That duplication spans
    a process boundary (a markdown prompt and a Python enum cannot import
    from each other) and is held in sync by
    ``tests/metrology/test_audit_skill_sync.py``, so drift fails CI.
    """

    ARCHITECTURAL_DECAY = "architectural-decay"
    CONSISTENCY_ROT = "consistency-rot"
    TYPE_CONTRACT_DEBT = "type-contract-debt"
    TEST_DEBT = "test-debt"
    DEPENDENCY_CONFIG_DEBT = "dependency-config-debt"
    PERFORMANCE_RESOURCE = "performance-resource"
    ERROR_HANDLING_OBSERVABILITY = "error-handling-observability"
    SECURITY_HYGIENE = "security-hygiene"
    DOCUMENTATION_DRIFT = "documentation-drift"
    OTHER = "other"


class AuditSeverity(StrEnum):
    """The audit's own severity scale.

    Deliberately disjoint from ``review.models.Severity`` — the two grade
    different things on different artifacts. Do not add a mapping between
    them; a test asserts the value sets stay disjoint.
    """

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AuditEffort(StrEnum):
    """Remediation effort as the audit estimates it."""

    S = "S"
    M = "M"
    L = "L"


class AuditFinding(BaseModel):
    """One normalized finding from one audit run.

    ``raw_category`` is populated **only** when the model emitted a category
    outside ``AuditCategory``; it preserves what was actually said so an
    out-of-vocabulary finding is retained and inspectable rather than
    silently coerced or dropped.

    ``location`` is recorded as the audit emitted it and is **not** verified
    against the filesystem — a deliberate divergence from the review
    parser's path checking. The count and class of findings is the
    measurement; a fabricated location does not corrupt it, and re-verifying
    every location across N runs x M projects is I/O the measurement does
    not need.
    """

    finding_id: str
    category: AuditCategory
    raw_category: str | None = None
    severity: AuditSeverity
    effort: AuditEffort | None = None
    location: str
    summary: str


class FloorStat(BaseModel):
    """The measured spread of one quantity across a variance series.

    ``stddev`` is the sample standard deviation. At the default n=3 it is a
    coarse figure, and every surface presenting it says so — it bounds
    interpretation of a later delta, it does not support a significance
    claim.
    """

    min: int
    max: int
    mean: float
    stddev: float


class AuditRun(BaseModel):
    """One complete audit of one project — an ``audit_finding`` payload.

    A run persists as a whole or not at all. There is no partial-run
    record: a hung, truncated, or unparseable run persists nothing, so it
    can never enter a noise floor as a spuriously low finding count.

    ``commit_sha`` and ``audit_prompt_hash`` are what make runs comparable —
    a variance series must agree on both, and the reduction refuses a series
    that does not rather than averaging across a code or instrument change.

    ``unnormalized_count`` records findings the parser could not normalize
    (e.g. an unrecognized severity). They are counted, never guessed at and
    never silently dropped.
    """

    run_id: str
    project_id: ProjectId
    commit_sha: str
    audit_prompt_hash: str
    model: str
    measured_at: datetime
    findings: list[AuditFinding]
    unnormalized_count: int = 0


class AuditNoiseFloor(BaseModel):
    """The measured run-to-run spread of the audit on unchanged code.

    Per-project at a pinned commit under one instrument — never one global
    number. A project without a floor is reported as "no floor measured"
    and never borrows another project's.

    ``n_runs`` is the number of runs **actually** reduced, which may be
    fewer than requested when runs failed.
    """

    project_id: ProjectId
    commit_sha: str
    audit_prompt_hash: str
    n_runs: int
    total: FloorStat
    per_category: dict[AuditCategory, FloorStat]
    measured_at: datetime


class MetrologyRecord(BaseModel):
    """The on-disk envelope: one JSON file per record in the store.

    ``record_type`` discriminates the payload. 320 writes ``"sample"``
    records; 322 writes ``"graduated_config"``; 323 writes
    ``"audit_finding"`` (an ``AuditRun``, findings inline) and
    ``"audit_noise_floor"``. Each addition is an optional sibling field, so
    the envelope shape stays backward compatible and ``schema_version``
    does not move — no store migration is needed.
    """

    schema_version: int
    record_type: str = RECORD_TYPE_SAMPLE
    sample: SampleVerdict | None = None
    graduated_config: GraduatedConfig | None = None
    audit_run: AuditRun | None = None
    audit_noise_floor: AuditNoiseFloor | None = None
