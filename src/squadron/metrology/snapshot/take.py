"""The snapshot orchestrator (slice 400, Data Flow; 403 D5).

``take_snapshot`` measures a clean HEAD and writes one record; ``take_snapshot_at``
measures any commit from a temp export. It depends only on the
adapter contract: the registry and the tool runner are arguments, so the CLI and 404
pass the defaults and tests pass fakes.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from squadron import __version__
from squadron.metrology.errors import SnapshotAdapterContractError
from squadron.metrology.identity import derive_project_id
from squadron.metrology.project_id import ProjectId
from squadron.metrology.snapshot.contract import (
    AdapterContext,
    AdapterRegistry,
    LanguageAdapter,
    ToolRunner,
)
from squadron.metrology.snapshot.export import export_commit, resolve_commit
from squadron.metrology.snapshot.files import (
    effective_exclusions,
    group_by_language,
    resolve_files,
)
from squadron.metrology.snapshot.preflight import (
    check_integrity,
    preflight,
    read_snapshot_config,
)
from squadron.metrology.snapshot_models import (
    AbsenceReason,
    CodeSnapshot,
    LanguageSnapshot,
    LengthLimits,
    Measurement,
    SnapshotMetric,
    SourceLanguage,
)
from squadron.metrology.store import MetrologyStore, snapshot_record_id

_logger = logging.getLogger(__name__)


def _absent(
    language: SourceLanguage, metric: SnapshotMetric, reason: AbsenceReason, detail: str
) -> Measurement:
    return Measurement(metric=metric, language=language, absent=reason, absent_detail=detail)


def _measure_language(
    language: SourceLanguage,
    adapter: LanguageAdapter | None,
    files: list[str],
    ctx: AdapterContext,
) -> LanguageSnapshot:
    if adapter is None:
        measurements = [
            _absent(
                language,
                metric,
                AbsenceReason.NO_ADAPTER,
                f"no adapter registered for {language.value}",
            )
            for metric in SnapshotMetric
        ]
        return LanguageSnapshot(
            language=language, file_count=len(files), adapter=None, measurements=measurements
        )
    measured = adapter.measure(ctx, files)
    returned = [m.metric for m in measured]
    if len(returned) != len(set(returned)) or frozenset(returned) != adapter.metrics:
        raise SnapshotAdapterContractError(
            f"The {language.value} adapter declared {sorted(m.value for m in adapter.metrics)} "
            f"but returned {sorted(m.value for m in returned)}. "
            "An adapter must return exactly one measurement per declared metric."
        )
    unsupported = [
        _absent(
            language,
            metric,
            AbsenceReason.METRIC_UNSUPPORTED,
            f"the {language.value} adapter doesn't measure {metric.value}",
        )
        for metric in SnapshotMetric
        if metric not in adapter.metrics
    ]
    return LanguageSnapshot(
        language=language,
        file_count=len(files),
        adapter=type(adapter).__name__,
        measurements=[*measured, *unsupported],
    )


def _measure_all(
    ctx: AdapterContext, registry: AdapterRegistry, files: list[str]
) -> list[LanguageSnapshot]:
    grouped = group_by_language(files)
    languages: list[LanguageSnapshot] = []
    for language in sorted(grouped, key=lambda lang: lang.value):
        _logger.info("Measuring %d %s file(s)", len(grouped[language]), language.value)
        languages.append(_measure_language(language, registry.get(language), grouped[language], ctx))
    return languages


def _assemble(
    project_id: ProjectId,
    commit_sha: str,
    limits: LengthLimits,
    exclusions: list[str],
    languages: list[LanguageSnapshot],
) -> CodeSnapshot:
    return CodeSnapshot(
        snapshot_id=snapshot_record_id(project_id, commit_sha),
        project_id=project_id,
        commit_sha=commit_sha,
        measured_at=datetime.now(UTC),
        squadron_version=__version__,
        limits=limits,
        exclusions=exclusions,
        languages=languages,
    )


def take_snapshot(
    repo_root: Path,
    registry: AdapterRegistry,
    runner: ToolRunner,
    store: MetrologyStore,
) -> CodeSnapshot:
    """Measure the clean HEAD of *repo_root* and write one ``code_snapshot`` record.

    Raises ``SnapshotPreflightError`` before any tool runs when the tree isn't clean
    or the config is invalid, and ``SnapshotIntegrityError`` (writing nothing) when the
    repo changed during measurement. ``derive_project_id``'s error propagates unchanged.
    """
    checked = preflight(repo_root)
    project_id = derive_project_id(str(repo_root))
    exclusions = effective_exclusions(checked.project_exclusions, registry.values())
    ctx = AdapterContext(
        repo_root=repo_root,
        environment_root=repo_root,
        limits=checked.limits,
        runner=runner,
        tool_timeout_s=checked.tool_timeout_s,
    )
    languages = _measure_all(ctx, registry, resolve_files(repo_root, exclusions))
    check_integrity(repo_root)
    snapshot = _assemble(project_id, checked.head_sha, checked.limits, exclusions, languages)
    store.write_snapshot(snapshot)
    return snapshot


def take_snapshot_at(
    repo_root: Path,
    commit: str,
    registry: AdapterRegistry,
    runner: ToolRunner,
    store: MetrologyStore,
) -> CodeSnapshot:
    """Measure any commit of *repo_root* in a temp export and write one ``code_snapshot`` record.

    The export is measured with the live checkout's tools and settings (403 D5), so the
    checkout's own state doesn't matter and there is no clean-tree check. The project id
    comes from the live ``repo_root``. ``SnapshotExportError`` is raised for an unknown
    revision or a failed export; nothing is written in that case.
    """
    sha = resolve_commit(repo_root, commit)
    config = read_snapshot_config(repo_root)
    project_id = derive_project_id(str(repo_root))
    exclusions = effective_exclusions(config.project_exclusions, registry.values())
    with export_commit(repo_root, sha, exclusions, repo_root) as exported:
        ctx = AdapterContext(
            repo_root=exported.root,
            environment_root=repo_root,
            limits=config.limits,
            runner=runner,
            tool_timeout_s=config.tool_timeout_s,
        )
        languages = _measure_all(ctx, registry, exported.files)
    snapshot = _assemble(project_id, sha, config.limits, exclusions, languages)
    store.write_snapshot(snapshot)
    return snapshot
