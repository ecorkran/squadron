"""Per-language coverage measurements from one report reading (slice 401, D4, D5).

``coverage.read_coverage`` reads the report once per adapter; each adapter passes its
own language and files here to get ``coverable_lines`` and ``covered_lines``.
"""

from __future__ import annotations

from collections.abc import Sequence

from squadron.metrology.snapshot.coverage import (
    CoverageAbsence,
    CoverageFailure,
    CoverageReading,
)
from squadron.metrology.snapshot.tool_support import absent
from squadron.metrology.snapshot_models import (
    AbsenceReason,
    Measurement,
    SnapshotMetric,
    SourceLanguage,
    ToolIdentity,
)

COBERTURA_TOOL_NAME = "cobertura"

_COVERAGE_METRICS = (SnapshotMetric.COVERABLE_LINES, SnapshotMetric.COVERED_LINES)


def _counting(report_path: str) -> str:
    return (
        f"lines listed in the Cobertura report {report_path} (coverable) and those it "
        "records with hits above zero (covered), per file; the report counts only if no "
        "tracked file has a newer mtime than it, which cannot detect a copied or touched "
        "report or a later change that only deletes files; the figures depend on the "
        "report file and its mtime, so the same commit can read differently in another "
        "checkout; Istanbul always writes version 0.1, so a change of coverage provider "
        "is not visible in the tool version"
    )


def _per_file_measurement(
    metric: SnapshotMetric,
    language: SourceLanguage,
    reading: CoverageReading,
    files: Sequence[str],
) -> Measurement:
    per_file: dict[str, int] = {}
    not_in_report: list[str] = []
    for path in files:
        entry = reading.files.get(path)
        if entry is None:
            not_in_report.append(path)
        elif metric is SnapshotMetric.COVERABLE_LINES:
            per_file[path] = len(entry.coverable)
        else:
            per_file[path] = len(entry.covered)
    return Measurement(
        metric=metric,
        language=language,
        tool=ToolIdentity(
            name=COBERTURA_TOOL_NAME,
            version=reading.producer_version,
            counting=_counting(reading.report_path),
        ),
        per_file=per_file,
        tool_ignored_files=not_in_report,
    )


def coverage_measurements(
    reading: CoverageReading | CoverageAbsence | CoverageFailure,
    language: SourceLanguage,
    files: Sequence[str],
) -> list[Measurement]:
    """``coverable_lines`` and ``covered_lines`` for *language*'s *files*.

    An absence becomes both metrics absent with its reason; a failure becomes both
    ``tool_failed``. Both were already logged at WARNING when the report was read.
    """
    if isinstance(reading, CoverageAbsence):
        return [
            absent(language, metric, reading.reason, reading.detail) for metric in _COVERAGE_METRICS
        ]
    if isinstance(reading, CoverageFailure):
        return [
            absent(language, metric, AbsenceReason.TOOL_FAILED, reading.detail)
            for metric in _COVERAGE_METRICS
        ]
    return [_per_file_measurement(metric, language, reading, files) for metric in _COVERAGE_METRICS]
