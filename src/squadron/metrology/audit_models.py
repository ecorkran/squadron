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

from datetime import datetime

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
    "DELTA_DISCLAIMER",
    "NO_FLOOR_MEASURED",
    "AuditCategory",
    "AuditEffort",
    "AuditFinding",
    "AuditNoiseFloor",
    "AuditRun",
    "AuditSeverity",
    "BaselineCell",
    "BaselineExclusionSummary",
    "BaselineReport",
    "DeltaCell",
    "DeltaReport",
    "FloorStat",
    "FreshnessResult",
    "PreemptionFragment",
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
    #: Runs the attached floor was reduced from, or ``None`` when no floor
    #: was measured. Presented alongside the spread so a coarse n=2 floor is
    #: never mistaken for a well-evidenced one.
    floor_n_runs: int | None = None
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


class PreemptionFragment(BaseModel):
    """Static guidance text generated once from a project's baseline.

    Frozen at generation: dispatch reads the written file, never the
    metrology store. The stamped ``audit_prompt_hash``/``measured_at`` are
    the *source baseline's*, which is what makes staleness detectable — a
    fragment generated under one instrument is not silently reused under
    another.
    """

    project_id: ProjectId
    audit_prompt_hash: str
    measured_at: datetime
    text: str


class FreshnessResult(BaseModel):
    """Whether a written fragment still matches the current baseline.

    "Absent" and "stale" are distinct states carried in ``note`` and
    distinguishable by ``fragment_audit_prompt_hash is None`` — a fragment
    that was never generated is not the same condition as one that has
    fallen behind, and conflating them would hide which corrective action
    is needed.
    """

    is_current: bool
    fragment_audit_prompt_hash: str | None
    current_audit_prompt_hash: str | None
    fragment_measured_at: datetime | None
    note: str


#: Fixed observational framing carried by every ``DeltaReport``. A delta is
#: an observation of two measurements, not evidence that the pre-emption
#: fragment caused the difference: nothing here controls for code change,
#: instrument drift, or run-to-run noise beyond the measured floor.
DELTA_DISCLAIMER = (
    "Observational only. This compares one fresh audit run against a stored "
    "baseline; it does not establish that any intervention caused the "
    "difference. Deltas smaller than the measured noise floor's observed "
    "spread are indistinguishable from run-to-run variation. Categories with "
    "no measured floor carry no interpretation at all."
)


class DeltaCell(BaseModel):
    """One issue class's before/after count, judged against its floor.

    ``within_floor`` is ``None`` — never ``False`` — when no floor was
    measured for the category. An unmeasured floor cannot license a
    significance claim in either direction.
    """

    category: AuditCategory
    baseline_count: int
    new_count: int
    delta: int
    floor: FloorStat | None = None
    within_floor: bool | None = None


class DeltaReport(BaseModel):
    """A fresh audit run compared to a stored baseline, floor-relative.

    Computed on demand from existing ``AuditRun``/``ProjectBaseline``
    records and never persisted — it is a view over measurements, not a
    measurement of its own.
    """

    project_id: ProjectId
    baseline_commit_sha: str
    new_commit_sha: str
    baseline_total: int
    new_total: int
    total_delta: int
    total_within_floor: bool | None = None
    cells: list[DeltaCell]
    disclaimer: str = DELTA_DISCLAIMER
