"""Store methods for ``code_review`` records (slice 402, D5)."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import pytest

from squadron.metrology.errors import MetrologyStoreError
from squadron.metrology.store import MetrologyStore, code_review_record_id
from tests.metrology.conftest import make_sample_verdict
from tests.metrology.snapshot.builders import make_project_id
from tests.metrology.test_review_models import make_finding, make_record


@pytest.fixture
def store(tmp_path: Path) -> MetrologyStore:
    return MetrologyStore(store_dir=tmp_path / "review-store")


PATH_A = "project-documents/user/reviews/947-review.code.a.md"
PATH_B = "project-documents/user/reviews/948-review.code.b.md"


def record_for(path: str, project: str = "github.com/manta/example-repo", **overrides: object):
    base = make_record()
    return base.model_copy(
        update={
            "project_id": make_project_id(project),
            "review_path": path,
            "record_id": code_review_record_id(make_project_id(project), path),
            **overrides,
        }
    )


def test_id_is_stable_and_differs_by_path_and_project() -> None:
    project = make_project_id()

    assert code_review_record_id(project, PATH_A) == code_review_record_id(project, PATH_A)
    assert code_review_record_id(project, PATH_A) != code_review_record_id(project, PATH_B)
    assert code_review_record_id(project, PATH_A) != code_review_record_id(
        make_project_id("github.com/manta/other"), PATH_A
    )
    assert code_review_record_id(project, PATH_A).startswith("codereview-")


def test_writing_twice_with_the_same_id_leaves_one_file_with_the_second_content(
    store: MetrologyStore,
) -> None:
    first = record_for(PATH_A)
    second = record_for(PATH_A, findings=[make_finding(), make_finding()])

    store.write_code_review(first)
    store.write_code_review(second)

    assert len(list(store.store_dir.glob("*.json"))) == 1
    assert store.list_code_reviews(make_project_id()) == [second]


def test_a_mismatched_id_raises(store: MetrologyStore) -> None:
    record = record_for(PATH_A).model_copy(update={"record_id": "codereview-wrong"})

    with pytest.raises(MetrologyStoreError, match="does not match"):
        store.write_code_review(record)

    assert list(store.store_dir.glob("*.json")) == []


def test_listing_filters_by_project_and_sorts_newest_first(store: MetrologyStore) -> None:
    older = record_for(PATH_A, reviewed_at=date(2026, 1, 1))
    newer = record_for(PATH_B, reviewed_at=date(2026, 2, 1))
    other_project = record_for(PATH_A, "github.com/manta/other")
    for record in (older, newer, other_project):
        store.write_code_review(record)

    listed = store.list_code_reviews(make_project_id())

    assert [r.review_path for r in listed] == [PATH_B, PATH_A]


def test_a_corrupt_sibling_is_skipped_with_a_warning(
    store: MetrologyStore, caplog: pytest.LogCaptureFixture
) -> None:
    store.write_code_review(record_for(PATH_A))
    (store.store_dir / "broken.json").write_text("{not json", encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        listed = store.list_code_reviews(make_project_id())

    assert len(listed) == 1
    assert "broken.json" in caplog.text


def test_an_existing_sample_record_still_loads_beside_a_code_review(
    store: MetrologyStore,
) -> None:
    store.write_code_review(record_for(PATH_A))
    sample = make_sample_verdict()
    store.write_sample(sample)

    assert len(store.list_code_reviews(make_project_id())) == 1
    assert store.load_record(sample.sample_id).sample is not None
