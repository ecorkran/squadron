"""The slice rollup report assembly (slice 403, D3, D8, D9; criteria 7, 8, 10)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest

from squadron.metrology.errors import SnapshotExportError
from squadron.metrology.quality_report.models import AuditFloorState
from squadron.metrology.quality_report.slice_report import build_slice_report, ensure_snapshot
from squadron.metrology.slice_range import RecordedLanding, SliceRangeResult
from squadron.metrology.slice_range_models import RangeUnresolvedReason, SliceLanding
from squadron.metrology.snapshot_models import CodeSnapshot
from squadron.metrology.store import MetrologyStore, code_review_record_id
from tests.metrology.conftest import make_audit_finding, make_audit_run, make_noise_floor
from tests.metrology.snapshot.builders import (
    make_code_snapshot,
    make_measured_snapshot,
    make_project_id,
)
from tests.metrology.test_review_models import make_record
from tests.metrology.test_slice_range_models import make_landing

PROJECT = make_project_id()
FIRST_BEFORE, FIRST_AFTER = "1" * 40, "2" * 40
SECOND_BEFORE, SECOND_AFTER = "3" * 40, "4" * 40


@pytest.fixture
def store(tmp_path: Path) -> MetrologyStore:
    return MetrologyStore(store_dir=tmp_path / "report-store")


def landing(before: str, after: str) -> SliceLanding:
    return make_landing(after).model_copy(update={"before_sha": before})


def resolved(index: int, *landings: SliceLanding) -> SliceRangeResult:
    return SliceRangeResult(index, [RecordedLanding(x, False) for x in landings], None)


TWO_LANDINGS = resolved(940, landing(FIRST_BEFORE, FIRST_AFTER), landing(SECOND_BEFORE, SECOND_AFTER))


def measured(commit: str) -> CodeSnapshot:
    return make_measured_snapshot(commit_sha=commit)


def exists_everywhere(sha: str) -> bool:
    return True


def store_review(store: MetrologyStore, slice_index: int, path: str) -> None:
    record = make_record().model_copy(
        update={
            "slice_index": slice_index,
            "review_path": path,
            "record_id": code_review_record_id(PROJECT, path),
        }
    )
    store.write_code_review(record)


def test_two_landings_are_reported_separately_oldest_first(store: MetrologyStore) -> None:
    report = build_slice_report(940, TWO_LANDINGS, store, PROJECT, exists_everywhere, measured)

    assert report.reason is None
    assert report.target == "main"
    assert [x.landing.after_sha for x in report.landings] == [FIRST_AFTER, SECOND_AFTER]
    for entry in report.landings:
        assert entry.comparisons
        assert entry.before is not None
        assert entry.before.commit_sha == entry.landing.before_sha
        assert entry.audit is not None


def test_a_missing_snapshot_is_taken_with_an_info_line_and_a_stored_one_is_reused(
    store: MetrologyStore, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    taken: list[str] = []

    def take_at(repo_root: Path, commit: str) -> CodeSnapshot:
        taken.append(commit)
        return make_code_snapshot(commit_sha=commit)

    with caplog.at_level(logging.INFO):
        fresh = ensure_snapshot("a" * 40, tmp_path, store, PROJECT, take_at)

    assert taken == ["a" * 40]
    assert any("a" * 12 in r.getMessage() for r in caplog.records if r.levelno == logging.INFO)
    store.write_snapshot(fresh)

    again = ensure_snapshot("a" * 40, tmp_path, store, PROJECT, take_at)

    assert taken == ["a" * 40]
    assert again == fresh


def test_a_landing_whose_commit_is_gone_says_so_and_the_rest_still_reports(
    store: MetrologyStore, caplog: pytest.LogCaptureFixture
) -> None:
    store_review(store, 940, "project-documents/user/reviews/940-review.code.a.md")

    with caplog.at_level(logging.WARNING):
        report = build_slice_report(
            940, TWO_LANDINGS, store, PROJECT, lambda sha: sha != FIRST_BEFORE, measured
        )

    gone, intact = report.landings
    assert gone.missing_commit == FIRST_BEFORE
    assert gone.comparisons == []
    assert intact.missing_commit is None
    assert intact.comparisons
    assert report.reviews is not None
    assert report.reviews.n_files == 1
    warning = next(r for r in caplog.records if r.levelno == logging.WARNING)
    assert "940" in warning.getMessage()
    assert FIRST_BEFORE in warning.getMessage()


def test_audit_with_both_runs_gives_a_delta_and_the_floor_state(store: MetrologyStore) -> None:
    store.write_audit_run(make_audit_run(run_id="audit-20261001-aaaaaaaa", commit_sha=FIRST_BEFORE))
    store.write_audit_run(
        make_audit_run(
            run_id="audit-20261002-bbbbbbbb",
            commit_sha=FIRST_AFTER,
            findings=[make_audit_finding(), make_audit_finding(finding_id="F002")],
            measured_at=datetime(2026, 10, 2, tzinfo=UTC),
        )
    )
    store.write_noise_floor(make_noise_floor(commit_sha=FIRST_BEFORE))

    report = build_slice_report(
        940,
        resolved(940, landing(FIRST_BEFORE, FIRST_AFTER)),
        store,
        PROJECT,
        exists_everywhere,
        measured,
    )

    audit = report.landings[0].audit
    assert audit is not None
    assert audit.delta is not None
    assert (audit.delta.baseline_total, audit.delta.new_total) == (1, 2)
    assert audit.floor_state in (AuditFloorState.WITHIN_FLOOR, AuditFloorState.BEYOND_FLOOR)
    assert audit.floor_n_runs == 3


def test_audit_with_a_run_missing_names_which_one_and_runs_nothing(store: MetrologyStore) -> None:
    store.write_audit_run(make_audit_run(run_id="audit-20261002-bbbbbbbb", commit_sha=FIRST_AFTER))

    report = build_slice_report(
        940,
        resolved(940, landing(FIRST_BEFORE, FIRST_AFTER)),
        store,
        PROJECT,
        exists_everywhere,
        measured,
    )

    audit = report.landings[0].audit
    assert audit is not None
    assert audit.delta is None
    assert audit.missing is not None
    assert FIRST_BEFORE[:12] in audit.missing
    assert FIRST_AFTER[:12] not in audit.missing


def test_audit_runs_under_different_prompts_are_not_compared(store: MetrologyStore) -> None:
    store.write_audit_run(
        make_audit_run(
            run_id="audit-20261001-aaaaaaaa", commit_sha=FIRST_BEFORE, audit_prompt_hash="1" * 64
        )
    )
    store.write_audit_run(
        make_audit_run(
            run_id="audit-20261002-bbbbbbbb", commit_sha=FIRST_AFTER, audit_prompt_hash="2" * 64
        )
    )

    report = build_slice_report(
        940,
        resolved(940, landing(FIRST_BEFORE, FIRST_AFTER)),
        store,
        PROJECT,
        exists_everywhere,
        measured,
    )

    audit = report.landings[0].audit
    assert audit is not None
    assert audit.delta is None
    assert audit.missing is not None
    assert "audit prompt" in audit.missing


def test_unresolved_slice_holds_only_the_reason(store: MetrologyStore) -> None:
    store_review(store, 388, "project-documents/user/reviews/388-review.code.a.md")
    unresolved = SliceRangeResult(388, [], RangeUnresolvedReason.REFLOG_UNAVAILABLE)

    report = build_slice_report(388, unresolved, store, PROJECT, exists_everywhere, measured)

    assert report.reason is RangeUnresolvedReason.REFLOG_UNAVAILABLE
    assert report.landings == []
    assert report.reviews is None


def test_reviews_are_filtered_to_the_slice(store: MetrologyStore) -> None:
    store_review(store, 940, "project-documents/user/reviews/940-review.code.a.md")
    store_review(store, 941, "project-documents/user/reviews/941-review.code.a.md")

    report = build_slice_report(940, TWO_LANDINGS, store, PROJECT, exists_everywhere, measured)

    assert report.reviews is not None
    assert report.reviews.n_files == 1


def test_a_failing_ensure_snapshot_propagates_so_there_is_no_half_report(
    store: MetrologyStore,
) -> None:
    def failing(commit: str) -> CodeSnapshot:
        raise SnapshotExportError(f"cannot export {commit}")

    with pytest.raises(SnapshotExportError, match="cannot export"):
        build_slice_report(940, TWO_LANDINGS, store, PROJECT, exists_everywhere, failing)
