"""Record models for deterministic code snapshots (slice 400).

A ``CodeSnapshot`` is one coarse record per (project, commit): every language
present, and for each exactly one ``Measurement`` per ``SnapshotMetric``. A metric
that can't be measured is *absent with a reason*, never zero. Metric identity (tool,
version, rule set, environment) is enforced by the model validators here, so a
malformed snapshot can't reach the store. The envelope field and record-type
constant stay in ``models.py``; this module sits beside it (as ``replay_models.py``
does) so the envelope can import it without a cycle.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from squadron.metrology.project_id import ProjectId

#: Rule-set source for a tool run with no config file. The tool version stands in
#: for the rule set; this is an explicit value, not a missing one (D2).
RULE_SET_SOURCE_TOOL_DEFAULTS = "tool-defaults"


class SnapshotMetric(StrEnum):
    """What a snapshot measures. 401 adds members; adapters absent-fill the rest."""

    FILE_LENGTH = "file_length"
    FUNCTION_LENGTH = "function_length"
    LINT_COUNT = "lint_count"
    TYPE_ERRORS = "type_errors"
    CYCLOMATIC_COMPLEXITY = "cyclomatic_complexity"
    DUPLICATED_LINES = "duplicated_lines"
    COVERED_LINES = "covered_lines"
    COVERABLE_LINES = "coverable_lines"


#: Metrics whose present measurement must name the rule set it ran under.
RULE_SET_METRICS = frozenset({SnapshotMetric.LINT_COUNT, SnapshotMetric.TYPE_ERRORS})


class SourceLanguage(StrEnum):
    """Languages recognised by file extension. Not every one has an adapter."""

    PYTHON = "python"
    TYPESCRIPT = "typescript"
    JAVASCRIPT = "javascript"
    SHELL = "shell"


class AbsenceReason(StrEnum):
    """Why a metric is absent."""

    NO_ADAPTER = "no_adapter"
    METRIC_UNSUPPORTED = "metric_unsupported"
    TOOL_MISSING = "tool_missing"
    TOOL_FAILED = "tool_failed"
    ENVIRONMENT_UNRESOLVED = "environment_unresolved"
    COVERAGE_NOT_CONFIGURED = "coverage_not_configured"
    REPORT_MISSING = "report_missing"
    REPORT_STALE = "report_stale"


class ToolIdentity(BaseModel):
    """The tool that produced a measurement, and how it counts."""

    name: str
    version: str
    counting: str


class RuleSetIdentity(BaseModel):
    """The config a lint or type tool ran under. ``content_hash`` is None for defaults."""

    source: str
    content_hash: str | None


class EnvironmentIdentity(BaseModel):
    """The resolved environment a type count depends on."""

    lockfile_path: str
    lockfile_sha256: str
    interpreter_version: str


class LengthLimits(BaseModel):
    """Project-declared length limits. Unset is None; squadron has no default."""

    max_file_lines: int | None = Field(gt=0)
    max_function_lines: int | None = Field(gt=0)
    limits_declared: bool

    @model_validator(mode="after")
    def _declared_flag_matches_limits(self) -> LengthLimits:
        any_set = self.max_file_lines is not None or self.max_function_lines is not None
        if self.limits_declared != any_set:
            raise ValueError("limits_declared must be true exactly when a limit is set")
        return self


class Distribution(BaseModel):
    """Count, total, min, p50, p90 and max over files, or over functions."""

    count: int
    total: int
    min: int
    p50: int
    p90: int
    max: int


class FunctionOverLimit(BaseModel):
    """A function longer than the declared limit."""

    path: str
    qualified_name: str
    start_line: int
    length: int


class Measurement(BaseModel):
    """One metric for one language: present with values, or absent with a reason."""

    metric: SnapshotMetric
    language: SourceLanguage
    tool: ToolIdentity | None = None
    rule_set: RuleSetIdentity | None = None
    environment: EnvironmentIdentity | None = None
    absent: AbsenceReason | None = None
    absent_detail: str | None = None
    per_file: dict[str, int] = Field(default_factory=dict)
    distribution: Distribution | None = None
    limit: int | None = None
    over_limit: list[FunctionOverLimit] = Field(default_factory=list[FunctionOverLimit])
    unparsed_files: list[str] = Field(default_factory=list)
    tool_ignored_files: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _enforce_identity(self) -> Measurement:
        """D2: identity rules, plus the absent-carries-nothing rule."""
        if self.absent is None:
            self._check_present()
        else:
            self._check_absent()
        self._normalize_order()
        return self

    def _check_present(self) -> None:
        if self.absent_detail is not None:
            raise ValueError("a present measurement must not carry absent_detail")
        if self.tool is None:
            raise ValueError("a present measurement requires a tool identity")
        if self.metric in RULE_SET_METRICS and self.rule_set is None:
            raise ValueError(f"a present {self.metric.value} measurement requires a rule_set")
        if self.metric is SnapshotMetric.TYPE_ERRORS and self.environment is None:
            raise ValueError("a present type_errors measurement requires an environment")

    def _check_absent(self) -> None:
        if not self.absent_detail:
            raise ValueError("an absent measurement requires absent_detail")
        carries_values = (
            self.per_file
            or self.over_limit
            or self.unparsed_files
            or self.tool_ignored_files
            or self.distribution is not None
            or self.limit is not None
        )
        if carries_values:
            raise ValueError("an absent measurement carries no values")

    def _normalize_order(self) -> None:
        """Sort every collection so serialized JSON is byte-stable across runs."""
        self.per_file = dict(sorted(self.per_file.items()))
        self.over_limit = sorted(
            self.over_limit, key=lambda row: (row.path, row.start_line, row.qualified_name)
        )
        self.unparsed_files = sorted(self.unparsed_files)
        self.tool_ignored_files = sorted(self.tool_ignored_files)


class LanguageSnapshot(BaseModel):
    """Every metric for one language present in the commit."""

    language: SourceLanguage
    file_count: int
    adapter: str | None
    measurements: list[Measurement]

    @model_validator(mode="after")
    def _one_measurement_per_metric(self) -> LanguageSnapshot:
        metrics = [m.metric for m in self.measurements]
        if len(set(metrics)) != len(metrics):
            raise ValueError(f"duplicate metric in {self.language.value} measurements")
        missing = set(SnapshotMetric) - set(metrics)
        if missing:
            names = ", ".join(sorted(m.value for m in missing))
            raise ValueError(f"{self.language.value} is missing metrics: {names}")
        wrong = [m for m in self.measurements if m.language is not self.language]
        if wrong:
            raise ValueError(f"measurement language does not match {self.language.value}")
        self.measurements = sorted(self.measurements, key=lambda m: m.metric.value)
        return self


class CodeSnapshot(BaseModel):
    """One snapshot of one commit of one project."""

    snapshot_id: str
    project_id: ProjectId
    commit_sha: str
    measured_at: datetime
    squadron_version: str
    limits: LengthLimits
    exclusions: list[str]
    languages: list[LanguageSnapshot]

    @model_validator(mode="after")
    def _normalize(self) -> CodeSnapshot:
        languages = [entry.language for entry in self.languages]
        if len(set(languages)) != len(languages):
            raise ValueError("duplicate language in snapshot")
        self.exclusions = sorted(set(self.exclusions))
        self.languages = sorted(self.languages, key=lambda entry: entry.language.value)
        return self
