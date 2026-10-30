"""The project rollup report (slice 403, D9)."""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.metrology.quality_report.project_report import build_project_report
from squadron.metrology.snapshot_models import SnapshotMetric
from squadron.metrology.store import MetrologyStore, code_review_record_id
from tests.metrology.conftest import make_audit_run, make_noise_floor
from tests.metrology.snapshot.builders import make_measured_snapshot, make_project_id
from tests.metrology.test_review_models import make_record

PROJECT = make_project_id()


@pytest.fixture
def store(tmp_path: Path) -> MetrologyStore:
    return MetrologyStore(store_dir=tmp_path / "project-store")


def store_review(store: MetrologyStore, slice_index: int | None, name: str) -> None:
    path = f"project-documents/user/reviews/{name}.md"
    store.write_code_review(
        make_record().model_copy(
            update={
                "slice_index": slice_index,
                "review_path": path,
                "record_id": code_review_record_id(PROJECT, path),
            }
        )
    )


def test_latest_snapshot_is_summarized_per_language_and_metric(store: MetrologyStore) -> None:
    store.write_snapshot(make_measured_snapshot(commit_sha="1" * 40))

    report = build_project_report(store, PROJECT, resolved_indices=set())

    assert report.snapshot_commit == "1" * 40
    lint = next(s for s in report.summaries if s.metric is SnapshotMetric.LINT_COUNT)
    assert lint.figure is not None
    assert lint.figure.total == 4


def test_audit_baseline_with_its_floor_is_included(store: MetrologyStore) -> None:
    store.write_audit_run(make_audit_run(commit_sha="1" * 40))
    store.write_noise_floor(make_noise_floor(commit_sha="1" * 40))

    report = build_project_report(store, PROJECT, resolved_indices=set())

    assert report.audit is not None
    [baseline] = report.audit.projects
    assert baseline.has_floor


def test_reviews_of_an_unresolved_slice_and_of_no_slice_are_project_only(
    store: MetrologyStore,
) -> None:
    store_review(store, 403, "403-review.code.a")
    store_review(store, 388, "388-review.code.a")
    store_review(store, None, "pr-review.code.a")

    report = build_project_report(store, PROJECT, resolved_indices={403})

    assert report.slice_reviews is not None
    assert report.slice_reviews.n_files == 1
    assert report.project_only_reviews is not None
    assert report.project_only_reviews.n_files == 2


def test_an_empty_project_says_so_in_every_section(store: MetrologyStore) -> None:
    report = build_project_report(store, PROJECT, resolved_indices=set())

    assert report.snapshot_commit is None
    assert report.summaries == []
    assert report.audit is None
    assert report.slice_reviews is not None
    assert (report.slice_reviews.n_files, report.project_only_reviews.n_files) == (0, 0)  # pyright: ignore[reportOptionalMemberAccess]


def test_another_projects_records_are_not_reported(store: MetrologyStore) -> None:
    store.write_audit_run(make_audit_run(project_value="github.com/manta/other"))

    assert build_project_report(store, PROJECT, resolved_indices=set()).audit is None
