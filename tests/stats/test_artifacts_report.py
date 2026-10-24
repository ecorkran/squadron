"""artifacts_usage_report: stamped planning artifacts as rows and per-kind totals (178 D5)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from squadron.pipeline.steps.phase import ArtifactKind
from squadron.stats.artifacts_report import artifacts_usage_report
from tests.events.builtin.usage_stamp_helpers import (
    ARCH_FRONT,
    ARCH_REL,
    DESIGN_REL,
    SLICE_FRONT,
    TASKS_FRONT,
    TASKS_REL,
    write_doc,
)

# Usage keys appended to real frontmatter, as the stamp writes them.
_STAMP = "turns: 3\ncostUsd: 0.5\ndurationSeconds: 4.0\nusageRounds: 2\npricedRounds: 1\n"


def _stamped(front: str, stamp: str = _STAMP) -> str:
    return front.removesuffix("---\n") + stamp + "---\n"


def _project(root: Path) -> None:
    write_doc(root, DESIGN_REL, _stamped(SLICE_FRONT))
    write_doc(
        root, TASKS_REL, _stamped(TASKS_FRONT, "costUsd: 0.25\nusageRounds: 1\npricedRounds: 1\n")
    )
    write_doc(root, ARCH_REL, _stamped(ARCH_FRONT))


def test_three_stamped_artifacts_give_three_rows(tmp_path: Path) -> None:
    _project(tmp_path)
    report = artifacts_usage_report(tmp_path, None)
    by_kind_and_slice = {(r.kind, r.slice) for r in report.rows}
    assert by_kind_and_slice == {
        (ArtifactKind.DESIGN, "178"),
        (ArtifactKind.TASKS, "178"),
        (ArtifactKind.DESIGN, "140"),
    }
    assert report.skipped == 0


def test_unstamped_files_produce_no_row_and_no_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    write_doc(tmp_path, DESIGN_REL, SLICE_FRONT)
    write_doc(tmp_path, TASKS_REL, TASKS_FRONT)
    with caplog.at_level(logging.WARNING):
        report = artifacts_usage_report(tmp_path, None)
    assert report.rows == () and report.by_kind == ()
    assert caplog.records == []


def test_unreadable_file_is_skipped_with_a_warning_naming_it(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _project(tmp_path)
    bad = tmp_path / DESIGN_REL.parent / "179-slice.broken.md"
    bad.write_text("no frontmatter here\n", encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        report = artifacts_usage_report(tmp_path, None)
    assert report.skipped == 1
    assert len(report.rows) == 3
    assert str(bad) in caplog.text


def test_slice_filter_excludes_other_slices(tmp_path: Path) -> None:
    _project(tmp_path)
    write_doc(tmp_path, DESIGN_REL.parent / "179-slice.other.md", _stamped(SLICE_FRONT))
    report = artifacts_usage_report(tmp_path, "179")
    assert [r.path.name for r in report.rows] == ["179-slice.other.md"]
    assert {r.slice for r in artifacts_usage_report(tmp_path, "178").rows} == {"178"}


def test_nested_subdirectories_are_not_read(tmp_path: Path) -> None:
    write_doc(tmp_path, DESIGN_REL.parent / "archive" / "178-slice.old.md", _stamped(SLICE_FRONT))
    write_doc(tmp_path, TASKS_REL.parent / "archive" / "178-tasks.old.md", _stamped(TASKS_FRONT))
    assert artifacts_usage_report(tmp_path, None).rows == ()


def test_per_kind_aggregate_sums_cost_and_rounds(tmp_path: Path) -> None:
    _project(tmp_path)
    by_kind = {k.kind: k for k in artifacts_usage_report(tmp_path, "178").by_kind}
    assert by_kind[ArtifactKind.DESIGN].cost_usd == 0.5
    assert (by_kind[ArtifactKind.DESIGN].rounds, by_kind[ArtifactKind.DESIGN].priced_rounds) == (2, 1)
    assert by_kind[ArtifactKind.TASKS].cost_usd == 0.25
    both = {k.kind: k for k in artifacts_usage_report(tmp_path, None).by_kind}
    assert both[ArtifactKind.DESIGN].cost_usd == pytest.approx(1.0)  # design + arch doc
    assert both[ArtifactKind.DESIGN].rounds == 4


def test_unpriced_only_kind_has_no_cost(tmp_path: Path) -> None:
    write_doc(tmp_path, DESIGN_REL, _stamped(SLICE_FRONT, "usageRounds: 2\npricedRounds: 0\n"))
    (kind_usage,) = artifacts_usage_report(tmp_path, "178").by_kind
    assert kind_usage.cost_usd is None and kind_usage.rounds == 2


def test_report_needs_no_run_state(tmp_path: Path) -> None:
    _project(tmp_path)
    assert not (tmp_path / ".squadron").exists()
    assert len(artifacts_usage_report(tmp_path, None).rows) == 3


def test_by_model_sums_shares_and_counts_unattributed_rounds(tmp_path: Path) -> None:
    """#267: the design's two rounds predate the split; the tasks' rounds name models."""
    write_doc(tmp_path, DESIGN_REL, _stamped(SLICE_FRONT))
    split = (
        "costUsd: 0.9\nusageRounds: 3\npricedRounds: 3\nusageByModel:\n"
        "  opus: {rounds: 1, costUsd: 0.6}\n  sonnet: {rounds: 2, costUsd: 0.3}\n"
    )
    write_doc(tmp_path, TASKS_REL, _stamped(TASKS_FRONT, split))

    report = artifacts_usage_report(tmp_path, None)

    assert [(m.model, m.rounds) for m in report.by_model] == [("opus", 1), ("sonnet", 2)]
    assert report.unattributed_rounds == 2
