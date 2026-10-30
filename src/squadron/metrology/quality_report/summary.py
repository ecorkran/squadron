"""A snapshot's headline figures, shared by the comparison and the project and history reports."""

from __future__ import annotations

from squadron.metrology.quality_report.models import LanguageMetricSummary, MetricFigure
from squadron.metrology.snapshot.lengths import files_over_limit
from squadron.metrology.snapshot_models import CodeSnapshot, Measurement, SnapshotMetric

#: Metrics whose sample is functions, not files.
_FUNCTION_METRICS = frozenset({SnapshotMetric.FUNCTION_LENGTH, SnapshotMetric.CYCLOMATIC_COMPLEXITY})


def measurement_figure(measurement: Measurement, file_count: int) -> MetricFigure | None:
    """The headline figure of a present measurement, else None.

    A measurement with a distribution is a spread over files or functions, and the
    distribution's count is the sample. Any other present measurement is a per-file
    total taken over all *file_count* files of its language.
    """
    if measurement.absent is not None:
        return None
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


def snapshot_summaries(snapshot: CodeSnapshot) -> list[LanguageMetricSummary]:
    """One summary per (language, metric), ordered by language then metric."""
    return [
        LanguageMetricSummary(
            language=entry.language,
            metric=measurement.metric,
            figure=measurement_figure(measurement, entry.file_count),
            absent=(
                f"{measurement.absent.value}: {measurement.absent_detail}"
                if measurement.absent is not None
                else None
            ),
        )
        for entry in snapshot.languages
        for measurement in entry.measurements
    ]
