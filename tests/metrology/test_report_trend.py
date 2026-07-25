"""Tests for the trend report."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from squadron.metrology.identity import derive_project_id, derive_result_ref
from squadron.metrology.report import trend_report
from squadron.review.models import Verdict

from .conftest import make_sample_verdict


def test_two_distinct_time_buckets_yield_two_ordered_series_entries(
    repo_with_remote: Path,
    write_review_file: Callable[..., Path],
) -> None:
    reviews_dir = repo_with_remote / "project-documents/user/reviews"
    review_file = write_review_file(reviews_dir, review_type="judge.slice-vs-arch")
    project_id = derive_project_id(str(repo_with_remote))
    result_ref = derive_result_ref(review_file, project_id, cwd=str(repo_with_remote))

    july_sample = make_sample_verdict(
        sample_id="sample-july",
        project_value=project_id.value,
        content_hash=result_ref.content_hash,
        artifact_level=None,
    ).model_copy(
        update={
            "result_ref": result_ref,
            "project_id": project_id,
            "captured_at": datetime(2026, 7, 10, tzinfo=UTC),
        }
    )
    august_sample = make_sample_verdict(
        sample_id="sample-august",
        project_value=project_id.value,
        content_hash=result_ref.content_hash,
        artifact_level=None,
    ).model_copy(
        update={
            "result_ref": result_ref,
            "project_id": project_id,
            "captured_at": datetime(2026, 8, 5, tzinfo=UTC),
        }
    )

    report = trend_report([july_sample, august_sample], str(repo_with_remote), bucket="month")

    assert [entry.bucket_label for entry in report.series] == ["2026-07", "2026-08"]


def test_each_series_entry_carries_same_grain_as_standalone_agreement_report(
    repo_with_remote: Path,
    write_review_file: Callable[..., Path],
) -> None:
    reviews_dir = repo_with_remote / "project-documents/user/reviews"
    review_file = write_review_file(reviews_dir, review_type="judge.slice-vs-arch")
    project_id = derive_project_id(str(repo_with_remote))
    result_ref = derive_result_ref(review_file, project_id, cwd=str(repo_with_remote))

    sample = make_sample_verdict(
        project_value=project_id.value,
        content_hash=result_ref.content_hash,
        artifact_level=None,
        human_verdict=Verdict.PASS,
    ).model_copy(
        update={
            "result_ref": result_ref,
            "project_id": project_id,
            "captured_at": datetime(2026, 7, 10, tzinfo=UTC),
        }
    )

    report = trend_report([sample], str(repo_with_remote), bucket="month")

    assert len(report.series) == 1
    bucket_agreement = report.series[0].agreement
    assert len(bucket_agreement.cells) == 1
    assert bucket_agreement.cells[0].n == 1
    assert bucket_agreement.cells[0].match_rate == 1.0


def test_bucket_override_changes_windowing(
    repo_with_remote: Path,
    write_review_file: Callable[..., Path],
) -> None:
    reviews_dir = repo_with_remote / "project-documents/user/reviews"
    review_file = write_review_file(reviews_dir, review_type="judge.slice-vs-arch")
    project_id = derive_project_id(str(repo_with_remote))
    result_ref = derive_result_ref(review_file, project_id, cwd=str(repo_with_remote))
    sample = make_sample_verdict(
        project_value=project_id.value,
        content_hash=result_ref.content_hash,
        artifact_level=None,
    ).model_copy(
        update={
            "result_ref": result_ref,
            "project_id": project_id,
            "captured_at": datetime(2026, 7, 10, tzinfo=UTC),
        }
    )

    month_report = trend_report([sample], str(repo_with_remote), bucket="month")
    day_report = trend_report([sample], str(repo_with_remote), bucket="day")

    assert month_report.series[0].bucket_label == "2026-07"
    assert day_report.series[0].bucket_label == "2026-07-10"


def test_default_bucket_comes_from_trend_bucket_config(
    repo_with_remote: Path,
    write_review_file: Callable[..., Path],
    write_project_config: Callable[[Path, dict[str, object]], Path],
) -> None:
    write_project_config(repo_with_remote, {"metrology.trend_bucket": "day"})
    reviews_dir = repo_with_remote / "project-documents/user/reviews"
    review_file = write_review_file(reviews_dir, review_type="judge.slice-vs-arch")
    project_id = derive_project_id(str(repo_with_remote))
    result_ref = derive_result_ref(review_file, project_id, cwd=str(repo_with_remote))
    sample = make_sample_verdict(
        project_value=project_id.value,
        content_hash=result_ref.content_hash,
        artifact_level=None,
    ).model_copy(
        update={
            "result_ref": result_ref,
            "project_id": project_id,
            "captured_at": datetime(2026, 7, 10, tzinfo=UTC),
        }
    )

    report = trend_report([sample], str(repo_with_remote))

    assert report.bucket == "day"
    assert report.series[0].bucket_label == "2026-07-10"


def test_empty_store_yields_empty_series_no_exception(repo_with_remote: Path) -> None:
    report = trend_report([], str(repo_with_remote), bucket="month")

    assert report.series == []
