"""Builders for code-snapshot records used across the snapshot tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from squadron.metrology.project_id import ProjectId, ProjectIdSource
from squadron.metrology.snapshot.contract import AdapterContext, ToolRunner
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
FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "snapshot"
#: Stands in for the capture's repo root in the stored tool output.
FIXTURE_ROOT_TOKEN = "__REPO_ROOT__"


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


def make_context(
    repo: Path,
    runner: ToolRunner,
    *,
    max_file: int | None = None,
    max_function: int | None = None,
    timeout_s: int = 5,
) -> AdapterContext:
    """An adapter context over *repo* with the given runner and optional limits."""
    return AdapterContext(
        repo_root=repo,
        limits=LengthLimits(
            max_file_lines=max_file,
            max_function_lines=max_function,
            limits_declared=max_file is not None or max_function is not None,
        ),
        runner=runner,
        tool_timeout_s=timeout_s,
    )


def read_fixture(name: str, repo_root: Path) -> str:
    """A captured tool output from ``tests/metrology/fixtures/snapshot``, rooted at *repo_root*."""
    text = (FIXTURES_DIR / name).read_text(encoding="utf-8")
    return text.replace(FIXTURE_ROOT_TOKEN, str(repo_root))
