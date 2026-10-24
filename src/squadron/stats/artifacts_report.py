"""Production cost stamped onto planning artifacts, read back for ``sq stats slice`` (178 D5).

Reads only frontmatter of the top-level slice designs, task files and architecture docs.
An artifact is a row only if a pipeline stamped it (``usageRounds``); older files are
skipped silently. The report never touches run state, so it survives ``sq runs prune``.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from squadron.core.usage import add_optional_float
from squadron.documents.frontmatter import read_frontmatter
from squadron.integrations.context_forge import ARCHITECTURE_DIR
from squadron.pipeline.steps.phase import ArtifactKind
from squadron.review.artifact_usage import USAGE_ROUNDS_KEY, ArtifactUsage, read_artifact_usage
from squadron.review.persistence import SLICES_DIR, TASKS_DIR
from squadron.stats.json_support import to_json_dict
from squadron.stats.reviews_report import leading_slice_index

_logger = logging.getLogger(__name__)

#: Where each kind of artifact lives and which files in it are artifacts (D5). The kind
#: comes from the directory, never the file name or ``docType``.
_SOURCES: tuple[tuple[ArtifactKind, Path, str], ...] = (
    (ArtifactKind.DESIGN, SLICES_DIR, "*.md"),
    (ArtifactKind.TASKS, TASKS_DIR, "*.md"),
    (ArtifactKind.DESIGN, Path(ARCHITECTURE_DIR), "*-arch.*.md"),
)


@dataclass(frozen=True)
class ArtifactUsageRow:
    path: Path
    kind: ArtifactKind  # from the directory (D5)
    slice: str | None
    usage: ArtifactUsage


@dataclass(frozen=True)
class KindUsage:
    """One kind's stamped total: cost of priced rounds, and how many rounds were priced."""

    kind: ArtifactKind
    cost_usd: float | None  # None when no round was priced; never $0
    rounds: int
    priced_rounds: int


@dataclass(frozen=True)
class ModelUsage:
    """One model's stamped rounds across the artifacts, and the cost of its priced ones (#267)."""

    model: str
    cost_usd: float | None  # None when none of its rounds was priced; never $0
    rounds: int


@dataclass(frozen=True)
class ArtifactsUsageReport:
    rows: tuple[ArtifactUsageRow, ...]
    by_kind: tuple[KindUsage, ...]  # only kinds with at least one stamped row
    skipped: int  # unreadable files
    by_model: tuple[ModelUsage, ...]  # costliest first
    unattributed_rounds: int  # stamped before the per-model split existed

    def to_json_dict(self) -> dict[str, object]:
        return to_json_dict(self)


def artifacts_usage_report(project_root: Path, slice_filter: str | None) -> ArtifactsUsageReport:
    """Stamped artifacts under ``project_root``, optionally only slice ``slice_filter``'s."""
    rows: list[ArtifactUsageRow] = []
    skipped = 0
    for kind, directory, pattern in _SOURCES:
        for path in sorted((project_root / directory).glob(pattern)):
            slice_index = leading_slice_index(path)
            if slice_filter is not None and slice_index != slice_filter:
                continue
            front = _read_front(path)
            if front is None:
                skipped += 1
                continue
            row = _row(path, kind, slice_index, front)
            if row is not None:
                rows.append(row)
    by_model = _by_model(rows)
    return ArtifactsUsageReport(
        rows=tuple(rows),
        by_kind=_by_kind(rows),
        skipped=skipped,
        by_model=by_model,
        unattributed_rounds=sum(r.usage.rounds for r in rows) - sum(m.rounds for m in by_model),
    )


def _read_front(path: Path) -> Mapping[str, object] | None:
    """The file's frontmatter; None, with a WARNING naming the path, when unreadable."""
    try:
        front = read_frontmatter(path)
    except (OSError, UnicodeDecodeError) as exc:
        _logger.warning("skipping artifact %s: %s", path, exc)
        return None
    if front is None:
        _logger.warning("skipping artifact with no readable frontmatter: %s", path)
    return front


def _row(
    path: Path, kind: ArtifactKind, slice_index: str | None, front: Mapping[str, object]
) -> ArtifactUsageRow | None:
    """The row for a stamped artifact; None when unstamped or its stamp is malformed."""
    if USAGE_ROUNDS_KEY not in front:
        return None
    usage = read_artifact_usage(path, front)
    return None if usage is None else ArtifactUsageRow(path, kind, slice_index, usage)


def _by_model(rows: list[ArtifactUsageRow]) -> tuple[ModelUsage, ...]:
    costs: dict[str, float | None] = {}
    rounds: dict[str, int] = {}
    for row in rows:
        for model, share in row.usage.by_model.items():
            costs[model] = add_optional_float(costs.get(model), share.cost_usd)
            rounds[model] = rounds.get(model, 0) + share.rounds
    totals = [ModelUsage(model, costs[model], rounds[model]) for model in rounds]
    return tuple(sorted(totals, key=lambda m: (-(m.cost_usd or 0.0), m.model)))


def _by_kind(rows: list[ArtifactUsageRow]) -> tuple[KindUsage, ...]:
    totals: list[KindUsage] = []
    for kind in ArtifactKind:
        group = [row.usage for row in rows if row.kind is kind]
        if not group:
            continue
        cost: float | None = None
        for usage in group:
            cost = add_optional_float(cost, usage.cost.cost_usd)
        totals.append(
            KindUsage(
                kind=kind,
                cost_usd=cost,
                rounds=sum(u.rounds for u in group),
                priced_rounds=sum(u.priced_rounds for u in group),
            )
        )
    return tuple(totals)
