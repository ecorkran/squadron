"""Builders for code-snapshot records used across the snapshot tests."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from squadron.metrology.project_id import ProjectId, ProjectIdSource
from squadron.metrology.snapshot.contract import AdapterContext, ToolRunner
from squadron.metrology.snapshot_models import (
    AbsenceReason,
    CodeSnapshot,
    EnvironmentIdentity,
    LanguageSnapshot,
    LengthLimits,
    Measurement,
    RuleSetIdentity,
    SnapshotMetric,
    SourceLanguage,
    ToolIdentity,
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
    environment_root: Path | None = None,
) -> AdapterContext:
    """An adapter context over *repo* with the given runner and optional limits.

    The environment root defaults to *repo* (an in-place snapshot).
    """
    return AdapterContext(
        repo_root=repo,
        environment_root=environment_root if environment_root is not None else repo,
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


TOOL = ToolIdentity(name="fake", version="1.0", counting="fake counting")


def present(metric: SnapshotMetric, language: SourceLanguage) -> Measurement:
    return Measurement(
        metric=metric,
        language=language,
        tool=TOOL,
        rule_set=RuleSetIdentity(source="fake.toml", content_hash="a" * 64),
        environment=EnvironmentIdentity(
            lockfile_path="uv.lock", lockfile_sha256="b" * 64, interpreter_version="3.12"
        ),
    )


class FakeAdapter:
    """Declares ``metrics``; returns ``reports`` (default: one present measurement each)."""

    def __init__(
        self,
        language: SourceLanguage,
        metrics: frozenset[SnapshotMetric],
        *,
        reports: list[SnapshotMetric] | None = None,
        convention_exclusions: tuple[str, ...] = (),
        write_into_repo: str | None = None,
    ) -> None:
        self.language = language
        self.metrics = metrics
        self.convention_exclusions = convention_exclusions
        self._reports = reports if reports is not None else sorted(metrics, key=lambda m: m.value)
        self._write_into_repo = write_into_repo
        self.calls: list[tuple[AdapterContext, list[str]]] = []

    def measure(self, ctx: AdapterContext, files: Sequence[str]) -> list[Measurement]:
        self.calls.append((ctx, list(files)))
        if self._write_into_repo is not None:
            (ctx.repo_root / self._write_into_repo).write_text("written\n", encoding="utf-8")
        return [present(metric, self.language) for metric in self._reports]
