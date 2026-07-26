"""The audit oracle's typed surface — one import site for 323's shapes.

Mirrors ``report_models.py`` (321) and ``calibration_models.py`` (322):
Pydantic models, not console text, so ``--json`` emits them verbatim.

Every shape here is defined in ``models.py`` and re-exported. That is the
322 layering correction applied transitively: ``AuditRun`` and
``AuditNoiseFloor`` are ``MetrologyRecord`` envelope payloads and must live
beside the envelope, and because they embed ``AuditFinding``, ``FloorStat``,
and the enums, defining *those* here would invert the dependency and
reintroduce the circular import the correction removed.

Two separations encoded in those definitions must not be collapsed:

``AuditSeverity`` is the audit's own ``critical/high/medium/low`` scale and
is **never** mapped onto ``review.models.Severity``
(``PASS/NOTE/CONCERN/FAIL``). The two vocabularies grade different things on
different artifacts; a mapping would manufacture an equivalence that does
not exist. ``tests/metrology/test_audit_models.py`` asserts they stay
disjoint.

``AuditCategory`` is closed, and ``OTHER`` is load-bearing rather than a
dumping ground — an out-of-vocabulary category is retained on
``AuditFinding.raw_category``, never dropped.
"""

from __future__ import annotations

from pydantic import BaseModel

from squadron.metrology.models import (
    AuditCategory,
    AuditEffort,
    AuditFinding,
    AuditNoiseFloor,
    AuditRun,
    AuditSeverity,
    FloorStat,
    ProjectId,
)

__all__ = [
    "AuditCategory",
    "AuditEffort",
    "AuditFinding",
    "AuditNoiseFloor",
    "AuditRun",
    "AuditSeverity",
    "BaselineCell",
    "BaselineExclusionSummary",
    "BaselineReport",
    "FloorStat",
    "ProjectBaseline",
]

#: Marker for a project audited but never variance-measured. Reported
#: verbatim so the absence of a floor is visible in output rather than
#: inferred from a missing field — a project never borrows another's number.
NO_FLOOR_MEASURED = "no floor measured"


class BaselineCell(BaseModel):
    """One project/issue-class cell: a count, with its floor if measured.

    ``floor`` is the applicable per-category ``FloorStat`` or ``None``. When
    it is ``None`` the cell carries ``floor_note`` (``"no floor measured"``)
    instead — never a figure borrowed from another project or another
    category.
    """

    category: AuditCategory
    count: int
    floor: FloorStat | None = None
    floor_note: str | None = None


class ProjectBaseline(BaseModel):
    """One project's baseline under one instrument.

    Scoped by ``audit_prompt_hash``: runs taken under different instruments
    are never pooled, so one project audited across a skill edit appears as
    two entries rather than one blended figure.
    """

    project_id: ProjectId
    commit_sha: str
    audit_prompt_hash: str
    run_id: str
    total_findings: int
    unnormalized_count: int
    total_floor: FloorStat | None = None
    floor_note: str | None = None
    cells: list[BaselineCell]

    @property
    def has_floor(self) -> bool:
        return self.total_floor is not None


class BaselineExclusionSummary(BaseModel):
    """What the report left out, so exclusions are never read as absence.

    Follows 321's ``ExclusionSummary`` precedent: a figure that is missing
    because data was filtered must be distinguishable from one that is
    missing because nothing was measured.
    """

    total_excluded: int = 0
    #: Projects whose runs span more than one instrument, reported
    #: separately per hash rather than pooled.
    projects_with_multiple_instruments: int = 0
    #: Project/instrument groups with no matching noise floor.
    groups_without_floor: int = 0


class BaselineReport(BaseModel):
    """The cross-project baseline at the project/issue-class grain.

    Carries **no agreement dimension** and no human-comparison figure of any
    kind. The audit oracle has no human counterpart; manufacturing one would
    be the overclaiming this initiative's architecture forbids.
    """

    projects: list[ProjectBaseline]
    excluded: BaselineExclusionSummary
