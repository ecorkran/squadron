"""Builders for code-snapshot records used across the snapshot tests."""

from __future__ import annotations

from datetime import UTC, datetime

from squadron.metrology.project_id import ProjectId, ProjectIdSource
from squadron.metrology.snapshot_models import (
    AbsenceReason,
    CodeSnapshot,
    LanguageSnapshot,
    LengthLimits,
    Measurement,
    SnapshotMetric,
    SourceLanguage,
)
from squadron.metrology.store import snapshot_record_id

PROJECT_VALUE = "github.com/manta/example-repo"


def make_project_id(value: str = PROJECT_VALUE) -> ProjectId:
    return ProjectId(value=value, source=ProjectIdSource.REMOTE)


def make_code_snapshot(
    *,
    project_value: str = PROJECT_VALUE,
    commit_sha: str = "c" * 40,
    measured_at: datetime | None = None,
) -> CodeSnapshot:
    """A valid snapshot: one Python section with every metric absent (`no_adapter`)."""
    project_id = make_project_id(project_value)
    measurements = [
        Measurement(
            metric=metric,
            language=SourceLanguage.PYTHON,
            absent=AbsenceReason.NO_ADAPTER,
            absent_detail="no adapter registered",
        )
        for metric in SnapshotMetric
    ]
    return CodeSnapshot(
        snapshot_id=snapshot_record_id(project_id, commit_sha),
        project_id=project_id,
        commit_sha=commit_sha,
        measured_at=measured_at if measured_at is not None else datetime(2026, 10, 22, tzinfo=UTC),
        squadron_version="0.23.8",
        limits=LengthLimits(max_file_lines=None, max_function_lines=None, limits_declared=False),
        exclusions=[],
        languages=[
            LanguageSnapshot(
                language=SourceLanguage.PYTHON,
                file_count=1,
                adapter=None,
                measurements=measurements,
            )
        ],
    )
