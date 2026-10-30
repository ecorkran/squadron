"""The report models behind ``sq metrology report slice|project|history`` (slice 403, D7-D9).

Each model is a view over stored measurements and is never persisted. No field combines
sources or metrics: a snapshot figure, an audit delta and a review count stay separate,
and nothing here is a score (a test asserts no serialized report has a key containing it).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel

from squadron.core.finding_categories import ReviewCategory
from squadron.metrology.audit_models import BaselineReport, DeltaReport
from squadron.metrology.project_id import ProjectId
from squadron.metrology.slice_range_models import RangeUnresolvedReason, SliceLanding
from squadron.metrology.snapshot_models import LengthLimits, SnapshotMetric, SourceLanguage
from squadron.review.models import Severity

#: Printed beside every review figure: no noise floor exists for review counts (D8).
NO_FLOOR_MEASURED = "no floor measured"


class ComparabilityBreak(StrEnum):
    """Why two measurements of one metric are not diffed (D7)."""

    TOOL_CHANGED = "tool_changed"
    RULE_SET_CHANGED = "rule_set_changed"
    ENVIRONMENT_CHANGED = "environment_changed"
    SETTINGS_CHANGED = "settings_changed"
    ABSENT_BEFORE = "absent_before"
    ABSENT_AFTER = "absent_after"


class BreakDetail(BaseModel):
    """One comparability break with what differs and, where one exists, the fix."""

    kind: ComparabilityBreak
    detail: str
    fix: str | None = None


class MetricFigure(BaseModel):
    """One measurement's headline figure with its sample size (D8).

    ``n`` counts what the figure was taken over: files, or functions for a metric
    measured per function. ``over_limit`` is None when no limit was declared.
    """

    total: int
    n: int
    n_unit: str
    over_limit: int | None = None
    limit: int | None = None


class MetricComparison(BaseModel):
    """One (language, metric) row of a before/after comparison.

    ``delta`` is set only when the row is comparable, which is exactly when ``breaks``
    is empty. ``source`` names the tool and rule set behind the after figure.
    """

    language: SourceLanguage
    metric: SnapshotMetric
    before: MetricFigure | None
    after: MetricFigure | None
    delta: int | None = None
    source: str | None = None
    breaks: list[BreakDetail]


class AuditFloorState(StrEnum):
    """Three states, never two: an unmeasured floor is neither within nor beyond it."""

    WITHIN_FLOOR = "within_floor"
    BEYOND_FLOOR = "beyond_floor"
    NO_FLOOR_MEASURED = "no_floor_measured"


class AuditSection(BaseModel):
    """A slice landing's audit delta, or which run is missing. An audit is never run here."""

    delta: DeltaReport | None = None
    missing: str | None = None
    floor_state: AuditFloorState | None = None
    floor_n_runs: int | None = None


class CategoryCount(BaseModel):
    """One review category's count, with the review-scale severities behind it."""

    category: ReviewCategory
    count: int
    severities: dict[Severity, int]
    #: The strings reviewers used, kept only for ``other`` so the vocabulary fit is visible.
    raw_categories: list[str]


class ReviewSection(BaseModel):
    """Counts over a set of ingested code reviews. Every figure is marked unfloored (D8)."""

    n_files: int
    n_findings: int
    write_time_findings: int
    read_side_mapped_findings: int
    categories: list[CategoryCount]
    #: Findings with no category. Counted here, never folded into ``other``.
    uncategorized: int
    #: Share of ``other`` among write-time findings; None when there are none.
    other_share: float | None
    floor_note: str = NO_FLOOR_MEASURED


class BoundarySettings(BaseModel):
    """The limits and exclusions one boundary snapshot was measured under."""

    commit_sha: str
    limits: LengthLimits
    exclusions: list[str]


class LandingReport(BaseModel):
    """One landing: static comparison, audit section and the settings of each boundary."""

    landing: SliceLanding
    #: Set when a boundary commit is gone from the repo; nothing else is then reported.
    missing_commit: str | None = None
    before: BoundarySettings | None = None
    after: BoundarySettings | None = None
    comparisons: list[MetricComparison] = []
    audit: AuditSection | None = None


class SliceReport(BaseModel):
    """A slice's rollup. An unresolved slice holds only its reason."""

    index: int
    target: str | None = None
    reason: RangeUnresolvedReason | None = None
    landings: list[LandingReport] = []
    reviews: ReviewSection | None = None


class LanguageMetricSummary(BaseModel):
    """The latest snapshot's figure for one (language, metric), or why it is absent."""

    language: SourceLanguage
    metric: SnapshotMetric
    figure: MetricFigure | None
    absent: str | None = None


class ProjectReport(BaseModel):
    """The project's current state: latest snapshot, latest audit baseline, reviews split."""

    project_id: ProjectId
    snapshot_commit: str | None = None
    summaries: list[LanguageMetricSummary] = []
    audit: BaselineReport | None = None
    slice_reviews: ReviewSection | None = None
    project_only_reviews: ReviewSection | None = None


class HistoryRow(BaseModel):
    """One snapshotted commit on the target's first-parent line."""

    commit_sha: str
    measured_at: datetime
    summaries: list[LanguageMetricSummary]
    #: Breaks between this row and the previous one; empty when comparable or first.
    breaks_from_previous: list[BreakDetail] = []


class HistoryReport(BaseModel):
    """Snapshots in first-parent order, with the count of snapshots off that line."""

    project_id: ProjectId
    rows: list[HistoryRow]
    off_line_snapshots: int
