"""The cross-project audit baseline.

Reads the store and writes nothing, mirroring ``report.py``'s discipline.
Every figure is presented with the floor that bounds its interpretation, or
with an explicit marker saying no floor was measured.

Three properties are structural rather than stylistic:

*No agreement dimension.* The audit oracle has no human counterpart, so
there is no match rate, no agreement figure, and nothing comparing the
audit to a person. A test asserts the serialized report contains no such
field.

*No borrowed floors.* A project without a measured floor is marked, never
given another project's number and never given a global default. Audit
variance plausibly scales with repo size and language, so a borrowed floor
would be a fabricated error bar.

*No cross-instrument pooling.* Runs group by ``audit_prompt_hash``, the
same discipline ``_comparability_key`` applies to judge configs. An edit to
the skill invalidates comparison across the edit.
"""

from __future__ import annotations

import logging

from squadron.metrology.audit_models import (
    NO_FLOOR_MEASURED,
    AuditCategory,
    BaselineCell,
    BaselineExclusionSummary,
    BaselineReport,
    ProjectBaseline,
)
from squadron.metrology.models import AuditNoiseFloor, AuditRun
from squadron.metrology.store import MetrologyStore

_logger = logging.getLogger(__name__)

#: A run's comparability group: one project under one instrument at one
#: commit. Runs from different groups are never pooled into one figure.
_GroupKey = tuple[str, str, str]


def _group_key(run: AuditRun) -> _GroupKey:
    return (run.project_id.value, run.commit_sha, run.audit_prompt_hash)


def _floor_key(floor: AuditNoiseFloor) -> _GroupKey:
    return (floor.project_id.value, floor.commit_sha, floor.audit_prompt_hash)


def baseline_report(
    store: MetrologyStore,
    *,
    project_filter: str | None = None,
    category_filter: AuditCategory | None = None,
) -> BaselineReport:
    """Build the cross-project baseline from persisted audit runs.

    Groups by ``(project_id, commit_sha, audit_prompt_hash)`` and reports
    the most recent run in each group, with that group's noise floor
    attached when one exists.

    The most recent run is used rather than an average across runs: a
    baseline is a point measurement of current state, and the *spread*
    across runs is what the floor already describes.
    """
    runs = store.list_audit_runs(project_id=project_filter)
    floors = {
        _floor_key(floor): floor for _, floor in store.list_noise_floors(project_id=project_filter)
    }

    # list_audit_runs returns newest first, so the first run seen for a group
    # is that group's most recent.
    latest_by_group: dict[_GroupKey, AuditRun] = {}
    for run in runs:
        latest_by_group.setdefault(_group_key(run), run)

    projects_by_id: dict[str, int] = {}
    for project_value, _, _ in latest_by_group:
        projects_by_id[project_value] = projects_by_id.get(project_value, 0) + 1

    excluded = BaselineExclusionSummary(
        projects_with_multiple_instruments=sum(1 for count in projects_by_id.values() if count > 1),
    )

    baselines: list[ProjectBaseline] = []
    for key, run in sorted(latest_by_group.items()):
        floor = floors.get(key)
        if floor is None:
            excluded.groups_without_floor += 1
            _logger.info(
                "No noise floor for %s at %s; reporting '%s'.",
                run.project_id.value,
                run.commit_sha[:8],
                NO_FLOOR_MEASURED,
            )

        counts: dict[AuditCategory, int] = {}
        for finding in run.findings:
            counts[finding.category] = counts.get(finding.category, 0) + 1

        cells: list[BaselineCell] = []
        for category in AuditCategory:
            if category_filter is not None and category is not category_filter:
                continue
            count = counts.get(category, 0)
            if count == 0 and category_filter is None:
                continue
            category_floor = floor.per_category.get(category) if floor is not None else None
            cells.append(
                BaselineCell(
                    category=category,
                    count=count,
                    floor=category_floor,
                    floor_note=None if category_floor is not None else NO_FLOOR_MEASURED,
                )
            )

        baselines.append(
            ProjectBaseline(
                project_id=run.project_id,
                commit_sha=run.commit_sha,
                audit_prompt_hash=run.audit_prompt_hash,
                run_id=run.run_id,
                total_findings=len(run.findings),
                unnormalized_count=run.unnormalized_count,
                total_floor=floor.total if floor is not None else None,
                floor_note=None if floor is not None else NO_FLOOR_MEASURED,
                cells=cells,
            )
        )

    excluded.total_excluded = excluded.groups_without_floor
    return BaselineReport(projects=baselines, excluded=excluded)
