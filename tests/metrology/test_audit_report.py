"""Baseline grouping, floor attachment, and the absence of an agreement axis.

Two assertions here are structural commitments rather than behavior checks:
the report must never grow an agreement dimension, and a project without a
measured floor must never be handed another project's number. Both are
asserted against the serialized output so a future field addition trips
them.
"""

from __future__ import annotations

import json

from squadron.metrology.audit_models import NO_FLOOR_MEASURED, AuditCategory, FloorStat
from squadron.metrology.audit_report import baseline_report
from squadron.metrology.store import MetrologyStore
from tests.metrology.conftest import make_audit_finding, make_audit_run, make_noise_floor


def _run_with_categories(
    *,
    run_id: str,
    project_value: str,
    categories: list[AuditCategory],
    commit_sha: str = "a" * 40,
    audit_prompt_hash: str = "b" * 64,
    unnormalized_count: int = 0,
):
    return make_audit_run(
        run_id=run_id,
        project_value=project_value,
        commit_sha=commit_sha,
        audit_prompt_hash=audit_prompt_hash,
        unnormalized_count=unnormalized_count,
        findings=[
            make_audit_finding(finding_id=f"F{index:03d}", category=category)
            for index, category in enumerate(categories)
        ],
    )


def test_groups_at_the_project_issue_class_grain(audit_store: MetrologyStore) -> None:
    """Two projects report separately, each with its own per-category counts."""
    audit_store.write_audit_run(
        _run_with_categories(
            run_id="audit-1",
            project_value="github.com/manta/alpha",
            categories=[
                AuditCategory.TEST_DEBT,
                AuditCategory.TEST_DEBT,
                AuditCategory.SECURITY_HYGIENE,
            ],
        )
    )
    audit_store.write_audit_run(
        _run_with_categories(
            run_id="audit-2",
            project_value="github.com/manta/beta",
            categories=[AuditCategory.DOCUMENTATION_DRIFT],
        )
    )

    report = baseline_report(audit_store)

    assert len(report.projects) == 2
    alpha = next(p for p in report.projects if p.project_id.value.endswith("alpha"))
    beta = next(p for p in report.projects if p.project_id.value.endswith("beta"))

    assert alpha.total_findings == 3
    assert {cell.category: cell.count for cell in alpha.cells} == {
        AuditCategory.TEST_DEBT: 2,
        AuditCategory.SECURITY_HYGIENE: 1,
    }
    assert beta.total_findings == 1


def test_floor_is_attached_when_measured(audit_store: MetrologyStore) -> None:
    audit_store.write_audit_run(
        _run_with_categories(
            run_id="audit-1",
            project_value="github.com/manta/alpha",
            categories=[AuditCategory.TEST_DEBT, AuditCategory.TEST_DEBT],
        )
    )
    audit_store.write_noise_floor(
        make_noise_floor(
            project_value="github.com/manta/alpha",
            total=FloorStat(min=1, max=3, mean=2.0, stddev=1.0),
            per_category={AuditCategory.TEST_DEBT: FloorStat(min=1, max=3, mean=2.0, stddev=1.0)},
        )
    )

    report = baseline_report(audit_store)
    alpha = report.projects[0]

    assert alpha.has_floor
    assert alpha.total_floor is not None
    assert alpha.total_floor.stddev == 1.0
    assert alpha.floor_note is None
    test_debt = next(c for c in alpha.cells if c.category is AuditCategory.TEST_DEBT)
    assert test_debt.floor is not None


def test_project_without_a_floor_is_marked_and_borrows_nothing(
    audit_store: MetrologyStore,
) -> None:
    """The measured project's numbers must not leak onto the unmeasured one.

    Audit variance plausibly scales with repo size and language, so a
    borrowed floor is a fabricated error bar — worse than an absent one,
    because it looks authoritative.
    """
    audit_store.write_audit_run(
        _run_with_categories(
            run_id="audit-1",
            project_value="github.com/manta/measured",
            categories=[AuditCategory.TEST_DEBT],
        )
    )
    audit_store.write_audit_run(
        _run_with_categories(
            run_id="audit-2",
            project_value="github.com/manta/unmeasured",
            categories=[AuditCategory.TEST_DEBT],
        )
    )
    audit_store.write_noise_floor(
        make_noise_floor(
            project_value="github.com/manta/measured",
            total=FloorStat(min=5, max=9, mean=7.0, stddev=2.0),
            per_category={AuditCategory.TEST_DEBT: FloorStat(min=5, max=9, mean=7.0, stddev=2.0)},
        )
    )

    report = baseline_report(audit_store)
    unmeasured = next(p for p in report.projects if p.project_id.value.endswith("unmeasured"))

    assert not unmeasured.has_floor
    assert unmeasured.total_floor is None
    assert unmeasured.floor_note == NO_FLOOR_MEASURED
    assert all(cell.floor is None for cell in unmeasured.cells)

    # No FloorStat of any kind reached the unmeasured project — asserted
    # structurally, since a borrowed floor would arrive as a populated
    # stddev field rather than as a recognizable marker.
    payload = json.loads(unmeasured.model_dump_json())
    assert payload["total_floor"] is None
    assert all(cell["floor"] is None for cell in payload["cells"])
    assert "stddev" not in unmeasured.model_dump_json()

    measured = next(p for p in report.projects if p.project_id.value == "github.com/manta/measured")
    assert measured.total_floor is not None, "the measured project keeps its own floor"
    assert report.excluded.groups_without_floor == 1


def test_cross_hash_runs_are_not_pooled(audit_store: MetrologyStore) -> None:
    """One project audited across a skill edit appears twice, never blended.

    audit_prompt_hash is the instrument's identity; an edit invalidates
    comparison across the edit, so pooling would average two different
    measurements into one meaningless figure.
    """
    audit_store.write_audit_run(
        _run_with_categories(
            run_id="audit-old",
            project_value="github.com/manta/alpha",
            categories=[AuditCategory.TEST_DEBT],
            audit_prompt_hash="1" * 64,
        )
    )
    audit_store.write_audit_run(
        _run_with_categories(
            run_id="audit-new",
            project_value="github.com/manta/alpha",
            categories=[AuditCategory.TEST_DEBT, AuditCategory.SECURITY_HYGIENE],
            audit_prompt_hash="2" * 64,
        )
    )

    report = baseline_report(audit_store)

    assert len(report.projects) == 2, "runs under different instruments must not pool"
    assert {p.audit_prompt_hash for p in report.projects} == {"1" * 64, "2" * 64}
    assert report.excluded.projects_with_multiple_instruments == 1


def test_report_emits_no_agreement_dimension(audit_store: MetrologyStore) -> None:
    """Structural: the audit oracle has no human counterpart to agree with.

    Asserted against the serialized payload rather than by eyeball, so a
    future field named ``match_rate`` or ``agreement`` fails here.
    """
    audit_store.write_audit_run(
        _run_with_categories(
            run_id="audit-1",
            project_value="github.com/manta/alpha",
            categories=[AuditCategory.TEST_DEBT],
        )
    )
    audit_store.write_noise_floor(make_noise_floor(project_value="github.com/manta/alpha"))

    serialized = json.dumps(json.loads(baseline_report(audit_store).model_dump_json())).lower()

    for forbidden in ("agreement", "match_rate", "human", "verdict", "concordance"):
        assert forbidden not in serialized, f"baseline must not carry a {forbidden!r} field"


def test_other_category_share_is_visible(audit_store: MetrologyStore) -> None:
    """A rising ``other`` share is the vocabulary-fit signal, so it must show."""
    audit_store.write_audit_run(
        _run_with_categories(
            run_id="audit-1",
            project_value="github.com/manta/alpha",
            categories=[
                AuditCategory.OTHER,
                AuditCategory.OTHER,
                AuditCategory.TEST_DEBT,
            ],
        )
    )

    report = baseline_report(audit_store)
    other = next(c for c in report.projects[0].cells if c.category is AuditCategory.OTHER)

    assert other.count == 2


def test_unnormalized_count_is_carried_through(audit_store: MetrologyStore) -> None:
    """Findings that could not be normalized stay visible in the baseline."""
    audit_store.write_audit_run(
        _run_with_categories(
            run_id="audit-1",
            project_value="github.com/manta/alpha",
            categories=[AuditCategory.TEST_DEBT],
            unnormalized_count=4,
        )
    )

    assert baseline_report(audit_store).projects[0].unnormalized_count == 4


def test_project_filter_scopes_the_report(audit_store: MetrologyStore) -> None:
    audit_store.write_audit_run(
        _run_with_categories(
            run_id="audit-1",
            project_value="github.com/manta/alpha",
            categories=[AuditCategory.TEST_DEBT],
        )
    )
    audit_store.write_audit_run(
        _run_with_categories(
            run_id="audit-2",
            project_value="github.com/manta/beta",
            categories=[AuditCategory.TEST_DEBT],
        )
    )

    report = baseline_report(audit_store, project_filter="github.com/manta/alpha")

    assert len(report.projects) == 1
    assert report.projects[0].project_id.value == "github.com/manta/alpha"


def test_category_filter_reports_zero_counts_explicitly(audit_store: MetrologyStore) -> None:
    """A filtered category with no findings reports 0, not an absent row.

    Asking about a category and getting silence is ambiguous; asking and
    getting zero is an answer.
    """
    audit_store.write_audit_run(
        _run_with_categories(
            run_id="audit-1",
            project_value="github.com/manta/alpha",
            categories=[AuditCategory.TEST_DEBT],
        )
    )

    report = baseline_report(audit_store, category_filter=AuditCategory.SECURITY_HYGIENE)
    cells = report.projects[0].cells

    assert len(cells) == 1
    assert cells[0].category is AuditCategory.SECURITY_HYGIENE
    assert cells[0].count == 0


def test_empty_store_yields_an_empty_report(audit_store: MetrologyStore) -> None:
    report = baseline_report(audit_store)

    assert report.projects == []
    assert report.excluded.total_excluded == 0


def test_latest_run_per_group_is_reported(audit_store: MetrologyStore) -> None:
    """A baseline is a point measurement; the spread is the floor's job."""
    from datetime import UTC, datetime

    audit_store.write_audit_run(
        _run_with_categories(
            run_id="audit-older",
            project_value="github.com/manta/alpha",
            categories=[AuditCategory.TEST_DEBT],
        ).model_copy(update={"measured_at": datetime(2026, 7, 1, tzinfo=UTC)})
    )
    audit_store.write_audit_run(
        _run_with_categories(
            run_id="audit-newer",
            project_value="github.com/manta/alpha",
            categories=[AuditCategory.TEST_DEBT, AuditCategory.OTHER],
        ).model_copy(update={"measured_at": datetime(2026, 7, 26, tzinfo=UTC)})
    )

    report = baseline_report(audit_store)

    assert len(report.projects) == 1
    assert report.projects[0].run_id == "audit-newer"
    assert report.projects[0].total_findings == 2
