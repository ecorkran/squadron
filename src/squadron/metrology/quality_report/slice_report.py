"""Assemble the slice rollup report (slice 403, D3, D8, D9).

Every dependency is passed in: the snapshot source, the commit-existence check and the
stores. A failing ``ensure_snapshot`` propagates, so there is never a half report, and no
audit is ever run here: the audit section reads stored runs only.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from squadron.metrology.audit_delta import compute_delta
from squadron.metrology.audit_models import AuditRun, ProjectBaseline
from squadron.metrology.audit_report import baseline_report
from squadron.metrology.models import ProjectId
from squadron.metrology.quality_report.compare import compare_snapshots
from squadron.metrology.quality_report.models import (
    AuditFloorState,
    AuditSection,
    BoundarySettings,
    LandingReport,
    SliceReport,
)
from squadron.metrology.quality_report.reviews import review_section
from squadron.metrology.slice_range import SliceRangeResult
from squadron.metrology.slice_range_models import SliceLanding
from squadron.metrology.snapshot_models import CodeSnapshot
from squadron.metrology.store import MetrologyStore

_logger = logging.getLogger(__name__)

_SHA_PREVIEW_CHARS = 12
_HASH_PREVIEW_CHARS = 8

#: Takes a commit and returns its snapshot, measuring it when none is stored.
EnsureSnapshot = Callable[[str], CodeSnapshot]
#: Measures one commit of the repo: ``take_snapshot_at`` with its other arguments bound.
TakeSnapshotAt = Callable[[Path, str], CodeSnapshot]
CommitExists = Callable[[str], bool]


def ensure_snapshot(
    commit: str,
    repo_root: Path,
    store: MetrologyStore,
    project_id: ProjectId,
    take_at: TakeSnapshotAt,
) -> CodeSnapshot:
    """The newest stored snapshot at *commit*, else a fresh one from *take_at*."""
    stored = store.list_snapshots(project_id, commit_sha=commit)
    if stored:
        return stored[0]
    _logger.info("No stored snapshot at %s; measuring it now", commit[:_SHA_PREVIEW_CHARS])
    return take_at(repo_root, commit)


def _settings(snapshot: CodeSnapshot) -> BoundarySettings:
    return BoundarySettings(
        commit_sha=snapshot.commit_sha, limits=snapshot.limits, exclusions=snapshot.exclusions
    )


def _latest_at(runs: list[AuditRun], commit: str) -> AuditRun | None:
    """The newest run at *commit*; ``list_audit_runs`` returns newest first."""
    return next((run for run in runs if run.commit_sha == commit), None)


def _audit_section(store: MetrologyStore, project_id: ProjectId, landing: SliceLanding) -> AuditSection:
    """The audit delta across the landing from stored runs, or which run is missing (D8)."""
    runs = store.list_audit_runs(project_id=project_id.value)
    before_sha, after_sha = landing.before_sha, landing.after_sha
    after_run = _latest_at(runs, after_sha)
    before_run = _latest_at(runs, before_sha)
    if after_run is None or before_run is None:
        missing = [
            f"no audit run at {sha[:_SHA_PREVIEW_CHARS]}"
            for sha, run in ((before_sha, before_run), (after_sha, after_run))
            if run is None
        ]
        return AuditSection(missing="; ".join(missing))
    # Runs under different instruments are never compared: pair on the after run's prompt.
    prompt = after_run.audit_prompt_hash
    paired = _latest_at([r for r in runs if r.audit_prompt_hash == prompt], before_sha)
    if paired is None:
        return AuditSection(
            missing=(
                f"no audit run at {before_sha[:_SHA_PREVIEW_CHARS]} under the audit prompt "
                f"{prompt[:_HASH_PREVIEW_CHARS]} used at {after_sha[:_SHA_PREVIEW_CHARS]}"
            )
        )
    baseline = _baseline_for(store, project_id, paired)
    if baseline is None:
        return AuditSection(missing=f"no audit baseline at {before_sha[:_SHA_PREVIEW_CHARS]}")
    delta = compute_delta(baseline, after_run)
    state = {
        True: AuditFloorState.WITHIN_FLOOR,
        False: AuditFloorState.BEYOND_FLOOR,
        None: AuditFloorState.NO_FLOOR_MEASURED,
    }[delta.total_within_floor]
    return AuditSection(delta=delta, floor_state=state, floor_n_runs=baseline.floor_n_runs)


def _baseline_for(
    store: MetrologyStore, project_id: ProjectId, run: AuditRun
) -> ProjectBaseline | None:
    report = baseline_report(store, project_filter=project_id.value)
    return next(
        (
            b
            for b in report.projects
            if b.commit_sha == run.commit_sha and b.audit_prompt_hash == run.audit_prompt_hash
        ),
        None,
    )


def _landing_report(
    index: int,
    landing: SliceLanding,
    store: MetrologyStore,
    project_id: ProjectId,
    commit_exists: CommitExists,
    ensure: EnsureSnapshot,
) -> LandingReport:
    for sha in (landing.before_sha, landing.after_sha):
        if not commit_exists(sha):
            _logger.warning("Slice %d: commit %s not found in the repository", index, sha)
            return LandingReport(landing=landing, missing_commit=sha)
    before, after = ensure(landing.before_sha), ensure(landing.after_sha)
    return LandingReport(
        landing=landing,
        before=_settings(before),
        after=_settings(after),
        comparisons=compare_snapshots(before, after),
        audit=_audit_section(store, project_id, landing),
    )


def build_slice_report(
    index: int,
    record_result: SliceRangeResult,
    store: MetrologyStore,
    project_id: ProjectId,
    commit_exists: CommitExists,
    ensure: EnsureSnapshot,
) -> SliceReport:
    """The report for one slice from its recorded range.

    An unresolved slice holds only its reason: no landings and no reviews, because
    without a range nothing is attributed to it (D9).
    """
    if not record_result.landings:
        return SliceReport(index=index, reason=record_result.reason)
    landings = [
        _landing_report(index, entry.landing, store, project_id, commit_exists, ensure)
        for entry in record_result.landings
    ]
    reviews = [r for r in store.list_code_reviews(project_id) if r.slice_index == index]
    return SliceReport(
        index=index,
        target=record_result.landings[0].landing.target_ref,
        landings=landings,
        reviews=review_section(reviews),
    )
