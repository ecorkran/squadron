"""Ingest of code-review files into the metrology store (slice 402, D5-D7)."""

from __future__ import annotations

import logging
import shutil
from datetime import date
from pathlib import Path

import pytest

from squadron.core.finding_categories import ReviewCategory
from squadron.metrology.errors import MetrologyStoreError, ReviewIngestInputError
from squadron.metrology.review_ingest import (
    IngestResult,
    _slice_index,  # pyright: ignore[reportPrivateUsage]
    ingest_reviews,
    resolve_review_files,
)
from squadron.metrology.review_models import CodeReviewRecord
from squadron.metrology.store import MetrologyStore
from squadron.review.models import Severity, Verdict
from tests.metrology.snapshot.builders import make_project_id

FIXTURES = Path(__file__).parent / "fixtures" / "review_ingest"
SLICE_947 = next(FIXTURES.glob("947-review.code.*")).name
SLICE_947_SHA = "c85beb2d702dc43fc194085d0dae47286cb805c2"


@pytest.fixture
def store(tmp_path: Path) -> MetrologyStore:
    return MetrologyStore(store_dir=tmp_path / "review-store")


@pytest.fixture
def reviews(tmp_path: Path) -> Path:
    """A writable copy of the fixture directory."""
    target = tmp_path / "reviews"
    shutil.copytree(FIXTURES, target)
    return target


def run(
    reviews: Path, store: MetrologyStore, repo_root: Path | None = None
) -> tuple[IngestResult, dict[str, CodeReviewRecord]]:
    project = make_project_id()
    result = IngestResult()
    files, _ = resolve_review_files([reviews], project, reviews)
    ingest_reviews(project, repo_root or reviews, files, store, result)
    records = {Path(r.review_path).name: r for r in store.list_code_reviews(project)}
    return result, records


def test_the_fixture_directory_is_classified(reviews: Path, store: MetrologyStore) -> None:
    result, records = run(reviews, store)

    assert set(records) == {
        "156-review.code.pipeline-executor-hardening.md",
        SLICE_947,
        "synthetic-pr-review.code.md",
        "synthetic-new-format.code.md",
        "synthetic-bad-severity.code.md",
    }
    assert result.ingested == 5
    assert result.skipped_not_code == 1  # the arch review
    assert result.skipped_unknown_verdict == 2  # the degraded PR review and 0-review
    assert {path.name for path, _ in result.failed} == {
        "synthetic-malformed-frontmatter.code.md",
        "synthetic-missing-verdict.code.md",
        "synthetic-new-format-bad-category.code.md",
    }


def test_failures_log_a_warning_with_the_path_and_the_rest_are_still_written(
    reviews: Path, store: MetrologyStore, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        result, records = run(reviews, store)

    for name in ("synthetic-malformed-frontmatter.code.md", "synthetic-missing-verdict.code.md"):
        assert any(name in record.getMessage() for record in caplog.records), name
    assert records, "the other files were still written"
    assert all(reason for _, reason in result.failed)


def test_the_947_record_carries_commit_slice_and_mapped_categories(
    reviews: Path, store: MetrologyStore
) -> None:
    _, records = run(reviews, store)
    record = records[SLICE_947]

    assert record.slice_index == 947
    assert record.commit_sha == SLICE_947_SHA
    assert record.read_side_mapped is True
    assert record.verdict is Verdict.CONCERNS
    categories = {f.raw_category: f.category for f in record.findings}
    assert categories["error-handling"] is ReviewCategory.ERROR_HANDLING_OBSERVABILITY


def test_a_historical_file_without_reviewed_sha_has_no_commit(
    reviews: Path, store: MetrologyStore
) -> None:
    _, records = run(reviews, store)
    record = records["156-review.code.pipeline-executor-hardening.md"]

    assert record.commit_sha is None
    assert record.slice_index == 156
    assert record.reviewed_at == date(2026, 4, 15)
    uncategorized = [f for f in record.findings if f.category is None]
    assert all(f.raw_category is None for f in uncategorized)


def test_a_pr_review_has_no_slice_index(reviews: Path, store: MetrologyStore) -> None:
    _, records = run(reviews, store)
    record = records["synthetic-pr-review.code.md"]

    assert record.slice_index is None
    assert record.commit_sha == "1" * 40


def test_new_format_file_keeps_write_time_categories(reviews: Path, store: MetrologyStore) -> None:
    _, records = run(reviews, store)
    record = records["synthetic-new-format.code.md"]

    assert record.read_side_mapped is False
    assert [(f.category, f.raw_category) for f in record.findings] == [
        (ReviewCategory.OTHER, "error-handling"),
        (ReviewCategory.SECURITY_HYGIENE, None),
        (None, None),
    ]


def test_an_unrecognized_severity_is_counted_and_dropped(reviews: Path, store: MetrologyStore) -> None:
    _, records = run(reviews, store)
    record = records["synthetic-bad-severity.code.md"]

    assert record.unnormalized_count == 1
    assert [f.finding_id for f in record.findings] == ["F001"]
    assert record.findings[0].severity is Severity.CONCERN


def test_a_non_code_review_is_skipped_whatever_its_verdict_but_a_code_review_is_checked(
    reviews: Path, store: MetrologyStore
) -> None:
    (reviews / "tasks-resolved.md").write_text(
        "---\nreviewType: tasks\nverdict: RESOLVED\n---\n", encoding="utf-8"
    )
    (reviews / "code-resolved.code.md").write_text(
        "---\nreviewType: code\nverdict: RESOLVED\ndateCreated: 20261001\n---\n", encoding="utf-8"
    )

    result, _ = run(reviews, store)

    assert result.skipped_not_code == 2
    failed = {path.name: reason for path, reason in result.failed}
    assert "unrecognized verdict" in failed["code-resolved.code.md"]
    assert "tasks-resolved.md" not in failed


def test_a_non_utf8_file_is_failed(reviews: Path, store: MetrologyStore) -> None:
    (reviews / "latin1.code.md").write_bytes(b"---\nreviewType: code\n---\n\xff\xfe")

    result, _ = run(reviews, store)

    assert "latin1.code.md" in {path.name for path, _ in result.failed}


def test_re_ingesting_after_an_edit_replaces_the_record(reviews: Path, store: MetrologyStore) -> None:
    run(reviews, store)
    target = reviews / SLICE_947
    target.write_text(
        target.read_text(encoding="utf-8").replace("findings:", "findings:\n  []\nold:", 1),
        encoding="utf-8",
    )
    synthetic = reviews / "synthetic-pr-review.code.md"
    synthetic.write_text(
        synthetic.read_text(encoding="utf-8").replace('summary: "finding 1"', 'summary: "edited"'),
        encoding="utf-8",
    )

    result, records = run(reviews, store)

    assert result.replaced == result.ingested == 5
    assert records["synthetic-pr-review.code.md"].findings[0].summary == "edited"
    assert records[SLICE_947].findings == []
    assert len(list(store.store_dir.glob("*.json"))) == 5


def test_a_nonexistent_path_raises_and_writes_nothing(tmp_path: Path, store: MetrologyStore) -> None:
    with pytest.raises(ReviewIngestInputError, match="nope"):
        resolve_review_files([tmp_path / "nope"], make_project_id(), tmp_path)

    assert not store.store_dir.exists() or list(store.store_dir.glob("*.json")) == []


def test_a_store_error_on_the_second_write_leaves_the_first_in_the_result(
    reviews: Path, store: MetrologyStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_write = store.write_code_review
    calls: list[str] = []

    def failing_second(record: CodeReviewRecord) -> str:
        calls.append(record.record_id)
        if len(calls) == 2:
            raise MetrologyStoreError("disk full")
        return real_write(record)

    monkeypatch.setattr(store, "write_code_review", failing_second)
    project = make_project_id()
    result = IngestResult()
    files, _ = resolve_review_files([reviews], project, reviews)

    with pytest.raises(MetrologyStoreError, match="disk full"):
        ingest_reviews(project, reviews, files, store, result)

    assert result.ingested == 1


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("project-documents/user/slices/947-slice.unattended-pipelines.md", 947),
        ("project-documents/user/tasks/402-tasks.code-review-normalization.md", 402),
        ("https://github.com/ecorkran/squadron/pull/116", None),
        ("", None),
        (None, None),
        ("project-documents/user/architecture/320-arch.judge.md", None),
    ],
)
def test_slice_index_comes_from_the_source_document_basename_only(
    source: str | None, expected: int | None
) -> None:
    assert _slice_index(source) == expected


def test_default_reviews_dir_with_no_paths_must_exist(tmp_path: Path) -> None:
    project = make_project_id()

    with pytest.raises(ReviewIngestInputError, match="doesn't exist"):
        resolve_review_files([], project, tmp_path)
