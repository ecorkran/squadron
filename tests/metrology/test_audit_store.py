"""Audit record persistence: round-trips, filters, and tolerant scanning.

Two properties matter beyond the round-trip. Filtering on
``audit_prompt_hash`` is the comparability guard — runs taken under
different instruments must be separable, or a variance series could pool
across an instrument change. And the scan must tolerate a corrupt sibling:
these stores accumulate records from many runs, and one bad file must not
make every query fail.
"""

from __future__ import annotations

import logging

import pytest

from squadron.metrology.store import (
    MetrologyStore,
    generate_audit_run_id,
    generate_noise_floor_id,
)
from tests.metrology.conftest import (
    make_audit_finding,
    make_audit_run,
    make_noise_floor,
    make_sample_verdict,
)


def test_generated_ids_have_the_documented_shape() -> None:
    run_id = generate_audit_run_id()
    floor_id = generate_noise_floor_id()
    assert run_id.startswith("audit-")
    assert floor_id.startswith("floor-")
    # audit-{YYYYMMDD}-{uuid8}
    _, stamp, suffix = run_id.split("-")
    assert len(stamp) == 8 and stamp.isdigit()
    assert len(suffix) == 8


def test_generated_ids_are_unique() -> None:
    assert generate_audit_run_id() != generate_audit_run_id()
    assert generate_noise_floor_id() != generate_noise_floor_id()


def test_write_then_list_audit_run(audit_store: MetrologyStore) -> None:
    run = make_audit_run(findings=[make_audit_finding(), make_audit_finding(finding_id="F002")])
    returned_id = audit_store.write_audit_run(run)

    assert returned_id == run.run_id
    listed = audit_store.list_audit_runs()
    assert listed == [run]
    assert len(listed[0].findings) == 2


def test_write_then_list_noise_floor(audit_store: MetrologyStore) -> None:
    floor = make_noise_floor()
    record_id = audit_store.write_noise_floor(floor)

    listed = audit_store.list_noise_floors()
    assert listed == [(record_id, floor)]


def test_noise_floor_replaced_in_place_by_record_id(audit_store: MetrologyStore) -> None:
    """Recomputing a floor updates its record rather than accumulating one."""
    record_id = audit_store.write_noise_floor(make_noise_floor(n_runs=2))
    audit_store.write_noise_floor(make_noise_floor(n_runs=5), record_id=record_id)

    listed = audit_store.list_noise_floors()
    assert len(listed) == 1
    assert listed[0][0] == record_id
    assert listed[0][1].n_runs == 5


def test_list_audit_runs_filters_by_project(audit_store: MetrologyStore) -> None:
    """Two projects' runs do not bleed into each other."""
    audit_store.write_audit_run(
        make_audit_run(run_id="audit-20260726-aaaaaaaa", project_value="github.com/manta/alpha")
    )
    audit_store.write_audit_run(
        make_audit_run(run_id="audit-20260726-bbbbbbbb", project_value="github.com/manta/beta")
    )

    alpha = audit_store.list_audit_runs(project_id="github.com/manta/alpha")
    assert [run.project_id.value for run in alpha] == ["github.com/manta/alpha"]


def test_list_audit_runs_filters_by_prompt_hash(audit_store: MetrologyStore) -> None:
    """The comparability guard: runs under differing instruments separate.

    Without this, a variance series could pool runs taken before and after a
    skill edit — averaging across an instrument change, which the reduction
    is required to refuse.
    """
    audit_store.write_audit_run(
        make_audit_run(run_id="audit-20260726-aaaaaaaa", audit_prompt_hash="1" * 64)
    )
    audit_store.write_audit_run(
        make_audit_run(run_id="audit-20260726-bbbbbbbb", audit_prompt_hash="2" * 64)
    )

    first = audit_store.list_audit_runs(audit_prompt_hash="1" * 64)
    assert [run.audit_prompt_hash for run in first] == ["1" * 64]


def test_list_noise_floors_filters_by_project(audit_store: MetrologyStore) -> None:
    audit_store.write_noise_floor(make_noise_floor(project_value="github.com/manta/alpha"))
    audit_store.write_noise_floor(make_noise_floor(project_value="github.com/manta/beta"))

    alpha = audit_store.list_noise_floors(project_id="github.com/manta/alpha")
    assert len(alpha) == 1
    assert alpha[0][1].project_id.value == "github.com/manta/alpha"


def test_corrupt_sibling_is_skipped_with_warning(
    audit_store: MetrologyStore, caplog: pytest.LogCaptureFixture
) -> None:
    """One unreadable record must not sink the whole scan."""
    run = make_audit_run()
    audit_store.write_audit_run(run)
    (audit_store.store_dir / "corrupt.json").write_text("{not json", encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        listed = audit_store.list_audit_runs()

    assert listed == [run]
    assert "Skipping unreadable metrology record" in caplog.text


def test_unknown_record_type_is_skipped_without_raising(audit_store: MetrologyStore) -> None:
    """A record type this version does not know is ignored, not fatal."""
    (audit_store.store_dir / "future.json").write_text(
        '{"schema_version": 1, "record_type": "something_from_the_future"}',
        encoding="utf-8",
    )
    assert audit_store.list_audit_runs() == []
    assert audit_store.list_noise_floors() == []


def test_record_types_coexist_without_bleeding(audit_store: MetrologyStore) -> None:
    """Samples, floors, and audit runs share a store and stay separable.

    The envelope discriminates on ``record_type`` *and* a non-None payload,
    so adding audit records to a store that already holds 320/322 records
    cannot cross-contaminate any list method.
    """
    audit_store.write_sample(make_sample_verdict())
    run = make_audit_run()
    audit_store.write_audit_run(run)
    floor = make_noise_floor()
    floor_id = audit_store.write_noise_floor(floor)

    assert audit_store.list_audit_runs() == [run]
    assert audit_store.list_noise_floors() == [(floor_id, floor)]
    assert len(audit_store.list_samples()) == 1
    assert audit_store.list_graduations() == []


def test_audit_runs_sort_newest_first(audit_store: MetrologyStore) -> None:
    from datetime import UTC, datetime

    older = make_audit_run(
        run_id="audit-20260701-aaaaaaaa", measured_at=datetime(2026, 7, 1, tzinfo=UTC)
    )
    newer = make_audit_run(
        run_id="audit-20260726-bbbbbbbb", measured_at=datetime(2026, 7, 26, tzinfo=UTC)
    )
    audit_store.write_audit_run(older)
    audit_store.write_audit_run(newer)

    assert [run.run_id for run in audit_store.list_audit_runs()] == [newer.run_id, older.run_id]
