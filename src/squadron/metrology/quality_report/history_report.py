"""The history rollup (slice 403): snapshots in the target's first-parent order."""

from __future__ import annotations

from collections.abc import Sequence

from squadron.metrology.models import ProjectId
from squadron.metrology.quality_report.compare import compare_snapshots
from squadron.metrology.quality_report.models import (
    BreakDetail,
    ComparabilityBreak,
    HistoryReport,
    HistoryRow,
)
from squadron.metrology.quality_report.summary import snapshot_summaries
from squadron.metrology.snapshot_models import CodeSnapshot
from squadron.metrology.store import MetrologyStore


def _breaks_between(previous: CodeSnapshot, current: CodeSnapshot) -> list[BreakDetail]:
    """Every distinct break between two snapshots, each naming its language and metric."""
    found: list[BreakDetail] = []
    for row in compare_snapshots(previous, current):
        if row.before is None and row.after is None:
            continue  # never measured at either commit: there is no series to break
        for detail in row.breaks:
            # A settings break applies to every row alike; the others belong to one metric.
            scoped = (
                detail
                if detail.kind is ComparabilityBreak.SETTINGS_CHANGED
                else detail.model_copy(
                    update={"detail": f"{row.language.value} {row.metric.value}: {detail.detail}"}
                )
            )
            if scoped not in found:
                found.append(scoped)
    return found


def build_history_report(
    store: MetrologyStore, project_id: ProjectId, first_parent_shas: Sequence[str]
) -> HistoryReport:
    """One row per snapshotted commit on the first-parent line, in the order given.

    *first_parent_shas* is the target's first-parent history, oldest first. The order
    comes from it, never from ``measured_at``. A row after the first carries the breaks
    that make it not comparable to the row before. Snapshots of commits off that line
    are counted, not listed.
    """
    latest_by_commit: dict[str, CodeSnapshot] = {}
    for snapshot in store.list_snapshots(project_id):  # newest first
        latest_by_commit.setdefault(snapshot.commit_sha, snapshot)
    on_line = [latest_by_commit[sha] for sha in first_parent_shas if sha in latest_by_commit]
    rows: list[HistoryRow] = []
    for position, snapshot in enumerate(on_line):
        rows.append(
            HistoryRow(
                commit_sha=snapshot.commit_sha,
                measured_at=snapshot.measured_at,
                summaries=snapshot_summaries(snapshot),
                breaks_from_previous=(
                    _breaks_between(on_line[position - 1], snapshot) if position > 0 else []
                ),
            )
        )
    return HistoryReport(
        project_id=project_id,
        rows=rows,
        off_line_snapshots=len(latest_by_commit) - len(on_line),
    )
