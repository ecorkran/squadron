"""Compare two code snapshots one measurement at a time (slice 403, D7).

Two measurements are diffed only when both are present and their tool, rule set and
environment are equal. Anything else carries every break that applies, named with what
differs, and no delta. A difference in the snapshots' limits or exclusions marks every
row, because exclusions change the file set and limits change the over-limit figures.
Each row is one language; languages are never compared with each other.
"""

from __future__ import annotations

from squadron.metrology.quality_report.models import (
    BreakDetail,
    ComparabilityBreak,
    MetricComparison,
    MetricFigure,
)
from squadron.metrology.snapshot.lengths import files_over_limit
from squadron.metrology.snapshot_models import (
    CodeSnapshot,
    LengthLimits,
    Measurement,
    SnapshotMetric,
    SourceLanguage,
)

#: Metrics whose sample is functions, not files.
_FUNCTION_METRICS = frozenset({SnapshotMetric.FUNCTION_LENGTH, SnapshotMetric.CYCLOMATIC_COMPLEXITY})
_HASH_PREVIEW_CHARS = 8
_NO_HASH = "defaults"

#: One side of a row: the measurement and the file count of its language, or None when
#: the snapshot has no files in that language.
_Side = tuple[Measurement, int] | None
_Key = tuple[SourceLanguage, SnapshotMetric]


def _index(snapshot: CodeSnapshot) -> dict[_Key, tuple[Measurement, int]]:
    return {
        (entry.language, measurement.metric): (measurement, entry.file_count)
        for entry in snapshot.languages
        for measurement in entry.measurements
    }


def _figure(side: _Side) -> MetricFigure | None:
    """The headline figure of a present measurement, else None."""
    if side is None or side[0].absent is not None:
        return None
    measurement, file_count = side
    distribution = measurement.distribution
    if distribution is None:
        return MetricFigure(total=sum(measurement.per_file.values()), n=file_count, n_unit="files")
    is_function = measurement.metric in _FUNCTION_METRICS
    if measurement.limit is None:
        over = None
    else:
        over = len(measurement.over_limit) if is_function else len(files_over_limit(measurement))
    return MetricFigure(
        total=distribution.total,
        n=distribution.count,
        n_unit="functions" if is_function else "files",
        over_limit=over,
        limit=measurement.limit,
    )


def _hash(value: str | None) -> str:
    return value[:_HASH_PREVIEW_CHARS] if value else _NO_HASH


def _absent_break(
    kind: ComparabilityBreak, side: _Side, language: SourceLanguage, which: str
) -> BreakDetail:
    if side is None:
        return BreakDetail(kind=kind, detail=f"no {language.value} files in the {which} snapshot")
    measurement = side[0]
    reason = measurement.absent.value if measurement.absent is not None else "unknown"
    return BreakDetail(kind=kind, detail=f"{reason}: {measurement.absent_detail}")


def _identity_breaks(before: Measurement, after: Measurement, remeasure: str) -> list[BreakDetail]:
    """The tool, rule set and environment differences between two present measurements."""
    breaks: list[BreakDetail] = []
    old, new = before.tool, after.tool
    if old is not None and new is not None and old != new:
        what = (
            f"{old.name} {old.version} -> {new.name} {new.version}"
            if (old.name, old.version) != (new.name, new.version)
            else f"{new.name} {new.version} counts differently"
        )
        breaks.append(BreakDetail(kind=ComparabilityBreak.TOOL_CHANGED, detail=what, fix=remeasure))
    if before.rule_set != after.rule_set:
        old_rules, new_rules = before.rule_set, after.rule_set
        old_text = f"{old_rules.source} {_hash(old_rules.content_hash)}" if old_rules else "none"
        new_text = f"{new_rules.source} {_hash(new_rules.content_hash)}" if new_rules else "none"
        breaks.append(
            BreakDetail(
                kind=ComparabilityBreak.RULE_SET_CHANGED,
                detail=f"{old_text} -> {new_text}",
            )
        )
    if before.environment != after.environment:
        old_env, new_env = before.environment, after.environment
        old_text = f"{old_env.lockfile_path} {_hash(old_env.lockfile_sha256)}" if old_env else "none"
        new_text = f"{new_env.lockfile_path} {_hash(new_env.lockfile_sha256)}" if new_env else "none"
        breaks.append(
            BreakDetail(
                kind=ComparabilityBreak.ENVIRONMENT_CHANGED,
                detail=f"{old_text} -> {new_text}",
                fix=remeasure,
            )
        )
    return breaks


def _limits_text(limits: LengthLimits) -> str:
    return f"file {limits.max_file_lines or 'none'}, function {limits.max_function_lines or 'none'}"


def _settings_break(before: CodeSnapshot, after: CodeSnapshot) -> BreakDetail | None:
    differences: list[str] = []
    if before.limits != after.limits:
        differences.append(f"limits {_limits_text(before.limits)} -> {_limits_text(after.limits)}")
    if before.exclusions != after.exclusions:
        added = sorted(set(after.exclusions) - set(before.exclusions))
        removed = sorted(set(before.exclusions) - set(after.exclusions))
        differences.append(f"exclusions +{added} -{removed}")
    if not differences:
        return None
    return BreakDetail(kind=ComparabilityBreak.SETTINGS_CHANGED, detail="; ".join(differences))


def _source(before: _Side, after: _Side) -> str | None:
    """The tool and rule set behind a row, preferring the after side."""
    for side in (after, before):
        if side is None:
            continue
        measurement = side[0]
        tool = measurement.tool
        if tool is None:
            continue
        rules = f", {measurement.rule_set.source}" if measurement.rule_set else ""
        return f"{tool.name} {tool.version}{rules}"
    return None


def compare_snapshots(before: CodeSnapshot, after: CodeSnapshot) -> list[MetricComparison]:
    """One row per (language, metric) present in either snapshot, ordered by language and metric."""
    old, new = _index(before), _index(after)
    settings = _settings_break(before, after)
    remeasure = (
        f"re-measure both with sq metrology snapshot --commit {before.commit_sha[:12]} "
        f"and --commit {after.commit_sha[:12]}"
    )
    rows: list[MetricComparison] = []
    for language, metric in sorted(
        old.keys() | new.keys(), key=lambda key: (key[0].value, key[1].value)
    ):
        before_side, after_side = old.get((language, metric)), new.get((language, metric))
        breaks: list[BreakDetail] = [settings] if settings is not None else []
        before_figure, after_figure = _figure(before_side), _figure(after_side)
        if before_figure is None:
            breaks.append(
                _absent_break(ComparabilityBreak.ABSENT_BEFORE, before_side, language, "before")
            )
        if after_figure is None:
            breaks.append(_absent_break(ComparabilityBreak.ABSENT_AFTER, after_side, language, "after"))
        if (
            before_side is not None
            and after_side is not None
            and before_figure is not None
            and after_figure is not None
        ):
            breaks.extend(_identity_breaks(before_side[0], after_side[0], remeasure))
        delta = (
            after_figure.total - before_figure.total
            if not breaks and before_figure is not None and after_figure is not None
            else None
        )
        rows.append(
            MetricComparison(
                language=language,
                metric=metric,
                before=before_figure,
                after=after_figure,
                delta=delta,
                source=_source(before_side, after_side),
                breaks=breaks,
            )
        )
    return rows
