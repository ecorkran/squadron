"""The project rollup (slice 403, D9): current state, with reviews split by attribution."""

from __future__ import annotations

from collections.abc import Collection

from squadron.metrology.audit_report import baseline_report
from squadron.metrology.models import ProjectId
from squadron.metrology.quality_report.models import ProjectReport
from squadron.metrology.quality_report.reviews import review_section, split_by_attribution
from squadron.metrology.quality_report.summary import snapshot_summaries
from squadron.metrology.store import MetrologyStore


def build_project_report(
    store: MetrologyStore, project_id: ProjectId, resolved_indices: Collection[int]
) -> ProjectReport:
    """Latest snapshot, latest audit baseline with its floor, and reviews split.

    A review is slice-attributed only when its slice is in *resolved_indices*; every other
    review is project-only. A project with no snapshot or no audit says so with an empty
    section (``snapshot_commit`` and ``audit`` are None), never with a made-up figure.
    """
    snapshots = store.list_snapshots(project_id)
    latest = snapshots[0] if snapshots else None
    baseline = baseline_report(store, project_filter=project_id.value)
    attributed, project_only = split_by_attribution(
        store.list_code_reviews(project_id), resolved_indices
    )
    return ProjectReport(
        project_id=project_id,
        snapshot_commit=latest.commit_sha if latest is not None else None,
        summaries=snapshot_summaries(latest) if latest is not None else [],
        audit=baseline if baseline.projects else None,
        slice_reviews=review_section(attributed),
        project_only_reviews=review_section(project_only),
    )
