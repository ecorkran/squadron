"""Human-readable summary of a ``CodeSnapshot`` for the CLI.

Pure formatting, kept out of the Typer module so it can be tested directly.
"""

from __future__ import annotations

from pathlib import Path

from squadron.metrology.preview import COMPACT_PREVIEW_CHARS, SHA_PREVIEW_CHARS
from squadron.metrology.snapshot.lengths import files_over_limit
from squadron.metrology.snapshot_models import (
    CodeSnapshot,
    Distribution,
    LanguageSnapshot,
    Measurement,
    SnapshotMetric,
)

#: Coverage metrics list files the report doesn't mention, not files a tool's ignores skipped.
_REPORT_METRICS = frozenset({SnapshotMetric.COVERABLE_LINES, SnapshotMetric.COVERED_LINES})
#: Metrics shown as a spread over functions rather than a per-file total.
_FUNCTION_SPREAD_METRICS = frozenset(
    {SnapshotMetric.FUNCTION_LENGTH, SnapshotMetric.CYCLOMATIC_COMPLEXITY}
)


def _spread(distribution: Distribution | None, unit: str) -> str:
    if distribution is None:
        return f"no {unit}s"
    return (
        f"{distribution.count} {unit}s, p50 {distribution.p50}, "
        f"p90 {distribution.p90}, max {distribution.max}"
    )


def _unparsed(measurement: Measurement) -> str:
    count = len(measurement.unparsed_files)
    return f"; {count} unparsed" if count else ""


def _summarize(measurement: Measurement) -> str:
    """One metric's summary, or ``absent: <reason> (<detail>)``."""
    if measurement.absent is not None:
        return f"absent: {measurement.absent.value} ({measurement.absent_detail})"
    tool = measurement.tool
    tool_text = f" [{tool.name} {tool.version}]" if tool is not None else ""
    if measurement.metric is SnapshotMetric.FILE_LENGTH:
        over = (
            f"; {len(files_over_limit(measurement))} over {measurement.limit}"
            if measurement.limit
            else ""
        )
        return f"{_spread(measurement.distribution, 'file')}{over}{tool_text}"
    if measurement.metric in _FUNCTION_SPREAD_METRICS:
        over = f"; {len(measurement.over_limit)} over {measurement.limit}" if measurement.limit else ""
        return (
            f"{_spread(measurement.distribution, 'function')}{over}{_unparsed(measurement)}{tool_text}"
        )
    total = sum(measurement.per_file.values())
    detail = f"{total} in {len(measurement.per_file)} file(s)"
    if measurement.rule_set is not None:
        detail += f", rules {measurement.rule_set.source}"
    if measurement.environment is not None:
        digest = measurement.environment.lockfile_sha256[:COMPACT_PREVIEW_CHARS]
        detail += f", {measurement.environment.lockfile_path} {digest}"
    if measurement.tool_ignored_files:
        reason = (
            "not in report"
            if measurement.metric in _REPORT_METRICS
            else "skipped by the tool's ignores"
        )
        detail += f"; {len(measurement.tool_ignored_files)} {reason}"
    return f"{detail}{_unparsed(measurement)}{tool_text}"


def _language_lines(entry: LanguageSnapshot) -> list[str]:
    header = f"{entry.language.value} ({entry.file_count} file(s))"
    return [header, *(f"  {m.metric.value}: {_summarize(m)}" for m in entry.measurements)]


def render_summary(snapshot: CodeSnapshot, record_path: Path, *, exported: bool = False) -> list[str]:
    """Lines to print: a section per language, then limits, exclusion count and record path.

    ``exported`` marks a snapshot measured from a temp export of the commit (403 D5).
    """
    limits = snapshot.limits
    if limits.limits_declared:
        declared = (
            f"file {limits.max_file_lines or 'none'}, function {limits.max_function_lines or 'none'}"
        )
    else:
        declared = "none declared"
    marker = " (exported)" if exported else ""
    lines = [
        f"snapshot of {snapshot.commit_sha[:SHA_PREVIEW_CHARS]}{marker} ({snapshot.project_id.value})"
    ]
    for entry in snapshot.languages:
        lines.extend(_language_lines(entry))
    lines.append(f"limits: {declared}")
    lines.append(f"exclusions: {len(snapshot.exclusions)}")
    lines.append(f"record: {record_path}")
    return lines
