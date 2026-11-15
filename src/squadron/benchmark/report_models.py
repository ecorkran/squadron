"""The benchmark report's models (slice 425 D13).

Every number is a measured signal shown beside the others; no field combines two signals into
one score, and a test reads this module's fields to keep it so. ``TableSection`` is the
generic container a case-kind table fills (its text lines and its data), so a new kind adds a
table without changing these models.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from squadron.benchmark.pair_row import PairRow
from squadron.benchmark.pairwise_models import PairwiseSection
from squadron.metrology.benchmark_models import CaseKind
from squadron.metrology.grade_records import SampleSizeEstimate


class ConfigIdentity(BaseModel):
    """A report row: 420's D6 identity, with the alias as its label (never a key)."""

    model_config = ConfigDict(frozen=True)

    label: str
    model: str
    profile: str | None
    effort_sent: str | None
    tool_use: bool | None
    max_output_tokens: int | None
    #: Set only on a row split because its identity spans prompt identities.
    prompt: str | None
    #: Canonical text of the identity, which a pair's seed is derived from.
    identity: str


class ObjectiveRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    config: ConfigIdentity
    n_cases: int
    samples: int
    mean_pass_fraction: float | None
    hidden_passed: int
    hidden_total: int
    regressions: int
    producer_new_passed: int
    producer_new_failed: int
    config_absences: dict[str, int]


class ReferenceLine(BaseModel):
    """The reference's own grade over the included cases; shown, never ranked."""

    model_config = ConfigDict(frozen=True)

    n_cases: int
    hidden_passed: int
    hidden_total: int
    regressions: int


class CheckRow(BaseModel):
    """Change from the case's baseline in lint and type totals, and the counted edits."""

    model_config = ConfigDict(frozen=True)

    config: ConfigIdentity
    mean_lint_delta: float | None
    mean_type_delta: float | None
    config_edits: int
    test_edits: int
    suppressions: int
    reinstalls: int


class FixTableData(BaseModel):
    """Sections 1-3 of the fix-case table."""

    model_config = ConfigDict(frozen=True)

    objective: tuple[ObjectiveRow, ...]
    reference: ReferenceLine | None
    paired: tuple[PairRow, ...]
    checks: tuple[CheckRow, ...]


class TableSection(BaseModel):
    """One case kind's sections 1-3: its rendered lines and the data they came from."""

    model_config = ConfigDict(frozen=True)

    kind: CaseKind
    lines: tuple[str, ...]
    data: dict[str, Any]


class FindingsRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    config: ConfigIdentity
    replays: int
    mean_by_severity: dict[str, float]
    mean_total: float | None
    # Findings the review returned with an off-scale severity; the means exclude them.
    unnormalized: int


class ReviewPair(BaseModel):
    """Cases whose difference in mean findings is beyond the case's own noise floor."""

    model_config = ConfigDict(frozen=True)

    label_a: str
    label_b: str
    a_more: int
    b_more: int
    within: int
    no_floor: int


class CostRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    config: ConfigIdentity
    producer_cost_mean: float | None
    producer_cost_total: float | None
    grading_cost_mean: float | None
    grading_cost_total: float | None
    turns_mean: float | None
    wall_seconds_mean: float | None
    wall_seconds_total: float
    unpriced_producer: int
    unpriced_grading: int


class AbsenceCount(BaseModel):
    model_config = ConfigDict(frozen=True)

    absence_class: str
    kind: str
    count: int


class BenchmarkReport(BaseModel):
    """What ``sq benchmark report`` shows, and what ``--json`` emits."""

    model_config = ConfigDict(frozen=True)

    benchmark_id: str
    case_set: str
    case_set_version: int
    grader_digest: str
    reviewer_alias: str
    review_floor_runs: int
    cases_in_set: int
    cases_compared: int
    #: Excluded cases by reason (``incomplete``, ``harness_replay`` ...).
    exclusions: dict[str, int]
    dropped_cases: int
    warnings: tuple[str, ...]
    older_identity_grades: int
    tables: tuple[TableSection, ...]
    review_flag: str
    findings: tuple[FindingsRow, ...]
    review_pairs: tuple[ReviewPair, ...]
    costs: tuple[CostRow, ...]
    absences: tuple[AbsenceCount, ...]
    stale_leak_scans: int
    unstamped_replays: dict[str, int]
    estimate: SampleSizeEstimate | None
    #: Slice cases only (slice 426); ``None`` leaves the text and JSON of other reports unchanged.
    pairwise: PairwiseSection | None = None
