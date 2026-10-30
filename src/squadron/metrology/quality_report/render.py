"""Plain-text renderers for the rollup reports (slice 403).

One renderer per report. Each returns lines and holds no logic beyond formatting; the
numbers and the breaks come from the report models unchanged.
"""

from __future__ import annotations

from squadron.metrology.quality_report.models import (
    AuditFloorState,
    AuditSection,
    BoundarySettings,
    BreakDetail,
    HistoryReport,
    LandingReport,
    LanguageMetricSummary,
    MetricComparison,
    MetricFigure,
    ProjectReport,
    ReviewSection,
    SliceReport,
)

_SHA = 8
_METRIC_WIDTH = 20
_CATEGORY_WIDTH = 30
_FLOOR_STATE_TEXT = {
    AuditFloorState.WITHIN_FLOOR: "within the noise floor",
    AuditFloorState.BEYOND_FLOOR: "beyond the noise floor",
    AuditFloorState.NO_FLOOR_MEASURED: "no floor measured",
}


def _figure_text(before: MetricFigure, after: MetricFigure, delta: int | None) -> str:
    pieces = [f"total {before.total:,} → {after.total:,}"]
    if delta is not None:
        pieces[0] += f" ({delta:+,})"
    if before.over_limit is not None and after.over_limit is not None:
        pieces.append(f"over {after.limit}: {before.over_limit} → {after.over_limit}")
    pieces.append(f"n={before.n:,} → {after.n:,} {after.n_unit}")
    return "  ".join(pieces)


def _break_text(breaks: list[BreakDetail]) -> str:
    return "not compared: " + "; ".join(f"{b.kind.value} ({b.detail})" for b in breaks)


def comparison_lines(rows: list[MetricComparison]) -> list[str]:
    """Rows grouped by language, the language named on its first row."""
    lines: list[str] = []
    previous_language = None
    for row in rows:
        language = row.language.value if row.language != previous_language else ""
        previous_language = row.language
        label = f"  {language:<8}{row.metric.value:<{_METRIC_WIDTH}}"
        if row.breaks or row.before is None or row.after is None:
            lines.append(f"{label}{_break_text(row.breaks)}")
            lines.extend(f"{' ' * len(label)}fix: {b.fix}" for b in row.breaks if b.fix)
            continue
        source = f"  [{row.source}]" if row.source else ""
        lines.append(f"{label}{_figure_text(row.before, row.after, row.delta)}{source}")
    return lines


def audit_lines(audit: AuditSection | None) -> list[str]:
    if audit is None:
        return []
    if audit.delta is None:
        return [f"  audit   {audit.missing}"]
    delta = audit.delta
    state = _FLOOR_STATE_TEXT[audit.floor_state or AuditFloorState.NO_FLOOR_MEASURED]
    runs = f", n_runs={audit.floor_n_runs}" if audit.floor_n_runs is not None else ""
    return [
        f"  audit   findings {delta.baseline_total} → {delta.new_total} "
        f"({delta.total_delta:+}); {state}{runs}"
    ]


def _settings_text(settings: BoundarySettings) -> str:
    limits = settings.limits
    declared = (
        f"file {limits.max_file_lines or 'none'}, function {limits.max_function_lines or 'none'}"
        if limits.limits_declared
        else "none declared"
    )
    return f"{settings.commit_sha[:_SHA]} limits {declared}; {len(settings.exclusions)} exclusions"


def _landing_lines(number: int, entry: LandingReport) -> list[str]:
    landing = entry.landing
    merge = f"merge {landing.merge_sha[:_SHA]}" if landing.merge_sha else "fast-forward"
    head = f"Landing {number}  {merge}"
    if entry.missing_commit is not None:
        return [f"{head}  commit {entry.missing_commit} not found"]
    lines = [f"{head}  before {landing.before_sha[:_SHA]} → after {landing.after_sha[:_SHA]}"]
    for settings in (entry.before, entry.after):
        if settings is not None:
            lines.append(f"  measured under {_settings_text(settings)}")
    lines.extend(comparison_lines(entry.comparisons))
    lines.extend(audit_lines(entry.audit))
    return lines


def review_lines(section: ReviewSection | None, heading: str = "Reviews") -> list[str]:
    if section is None:
        return []
    lines = [
        f"{heading} (by source document; {section.floor_note})",
        f"  n={section.n_files} review files, {section.n_findings} findings "
        f"(write-time {section.write_time_findings}, "
        f"read-side mapped {section.read_side_mapped_findings})",
    ]
    for category in section.categories:
        severities = ", ".join(f"{sev.value} {n}" for sev, n in sorted(category.severities.items()))
        raw = f"  raw: {', '.join(category.raw_categories)}" if category.raw_categories else ""
        name = category.category.value
        lines.append(f"  {name:<{_CATEGORY_WIDTH}}{category.count:>3}   ({severities}){raw}")
    if section.uncategorized:
        lines.append(f"  {'uncategorized':<{_CATEGORY_WIDTH}}{section.uncategorized:>3}")
    if section.other_share is not None:
        lines.append(f"  other is {section.other_share:.0%} of write-time findings")
    return lines


def render_slice_report(report: SliceReport) -> list[str]:
    """The slice report: header, each landing, then the slice's reviews."""
    if report.reason is not None:
        return [f"Slice {report.index} — unresolved: {report.reason.value}"]
    count = len(report.landings)
    noun = "landing" if count == 1 else "landings"
    lines = [f"Slice {report.index} — {count} {noun} on {report.target}"]
    for number, entry in enumerate(report.landings, start=1):
        lines.extend(_landing_lines(number, entry))
    lines.extend(review_lines(report.reviews))
    return lines


def _summary_text(summary: LanguageMetricSummary) -> str:
    label = f"{summary.language.value}.{summary.metric.value}"
    if summary.figure is None:
        return f"{label}=absent"
    return f"{label}={summary.figure.total:,} (n={summary.figure.n:,} {summary.figure.n_unit})"


def render_project_report(report: ProjectReport) -> list[str]:
    """The project report: latest snapshot, audit baseline, then reviews split by attribution."""
    if report.snapshot_commit is None:
        lines = [f"Project {report.project_id.value} — no snapshot recorded"]
    else:
        lines = [f"Project {report.project_id.value} — latest snapshot {report.snapshot_commit[:_SHA]}"]
        lines.extend(f"  {_summary_text(summary)}" for summary in report.summaries)
    if report.audit is None:
        lines.append("Audit baseline: no audit run recorded")
    else:
        lines.append("Audit baseline")
        for baseline in report.audit.projects:
            floor = (
                f"floor {baseline.total_floor.min}–{baseline.total_floor.max} "
                f"(n_runs={baseline.floor_n_runs})"
                if baseline.total_floor is not None
                else "no floor measured"
            )
            lines.append(
                f"  {baseline.commit_sha[:_SHA]}  prompt {baseline.audit_prompt_hash[:_SHA]}  "
                f"{baseline.total_findings} findings; {floor}"
            )
    lines.extend(review_lines(report.slice_reviews, "Reviews attributed to a slice"))
    lines.extend(review_lines(report.project_only_reviews, "Reviews attributed to the project only"))
    return lines


def render_history_report(report: HistoryReport) -> list[str]:
    """The history report: one block per snapshotted commit, with break markers between."""
    lines = [f"History — {len(report.rows)} snapshots on the first-parent line"]
    for row in report.rows:
        if row.breaks_from_previous:
            lines.append(f"  --- {_break_text(row.breaks_from_previous)} ---")
        lines.append(f"  {row.commit_sha[:_SHA]}  {row.measured_at:%Y-%m-%d}")
        lines.extend(f"    {_summary_text(summary)}" for summary in row.summaries)
    if report.off_line_snapshots:
        lines.append(f"{report.off_line_snapshots} snapshots of commits off this line not shown")
    return lines
