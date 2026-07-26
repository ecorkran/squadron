"""Noise-floor reduction: known values, zero-fill, and the refusal paths.

The refusals carry as much weight as the arithmetic. A floor is read by 324
as the error bar on every later delta, so a series that silently averaged
across a code change or an instrument edit would make an unrelated number
look authoritative — worse than having no floor at all.
"""

from __future__ import annotations

import statistics

import pytest

from squadron.metrology.audit_variance import AuditVarianceError, reduce_noise_floor
from squadron.metrology.models import AuditCategory, AuditRun
from tests.metrology.conftest import make_audit_finding, make_audit_run


def _run_with(
    *,
    run_id: str,
    categories: list[AuditCategory],
    commit_sha: str = "a" * 40,
    audit_prompt_hash: str = "b" * 64,
    project_value: str = "github.com/manta/example-repo",
) -> AuditRun:
    """One run whose findings land in the given categories, one each."""
    return make_audit_run(
        run_id=run_id,
        commit_sha=commit_sha,
        audit_prompt_hash=audit_prompt_hash,
        project_value=project_value,
        findings=[
            make_audit_finding(finding_id=f"F{index:03d}", category=category)
            for index, category in enumerate(categories)
        ],
    )


def _runs_of_size(counts: list[int]) -> list[AuditRun]:
    """A series whose runs have the given finding counts, all same category."""
    return [
        _run_with(
            run_id=f"audit-20260726-{index:08d}",
            categories=[AuditCategory.ARCHITECTURAL_DECAY] * count,
        )
        for index, count in enumerate(counts)
    ]


def test_known_value_reduction() -> None:
    """The design's worked example: 40/47/44 findings across three runs."""
    floor = reduce_noise_floor(_runs_of_size([40, 47, 44]))

    assert floor.total.min == 40
    assert floor.total.max == 47
    assert floor.total.mean == pytest.approx(statistics.fmean([40, 47, 44]))
    assert floor.total.stddev == pytest.approx(statistics.stdev([40, 47, 44]))
    assert floor.n_runs == 3


def test_floor_carries_the_series_identity() -> None:
    floor = reduce_noise_floor(_runs_of_size([10, 12]))

    assert floor.project_id.value == "github.com/manta/example-repo"
    assert floor.commit_sha == "a" * 40
    assert floor.audit_prompt_hash == "b" * 64


def test_per_category_zero_fills_an_absent_category() -> None:
    """A category absent from one run counts as 0 for that run, not missing.

    This is the denominator-correctness check. Dropping the run instead
    would compute the spread over two points rather than three and
    understate exactly the variance being measured.
    """
    runs = [
        _run_with(
            run_id="audit-1",
            categories=[AuditCategory.TEST_DEBT, AuditCategory.TEST_DEBT],
        ),
        _run_with(run_id="audit-2", categories=[AuditCategory.SECURITY_HYGIENE]),
        _run_with(
            run_id="audit-3",
            categories=[AuditCategory.TEST_DEBT, AuditCategory.TEST_DEBT],
        ),
    ]

    floor = reduce_noise_floor(runs)
    test_debt = floor.per_category[AuditCategory.TEST_DEBT]

    assert test_debt.min == 0, "the run lacking this category must count as zero"
    assert test_debt.max == 2
    assert test_debt.mean == pytest.approx(statistics.fmean([2, 0, 2]))
    assert test_debt.stddev == pytest.approx(statistics.stdev([2, 0, 2]))


def test_categories_absent_from_every_run_are_omitted() -> None:
    """Only categories the audit actually produced appear in the floor."""
    floor = reduce_noise_floor(_runs_of_size([3, 4]))

    assert AuditCategory.ARCHITECTURAL_DECAY in floor.per_category
    assert AuditCategory.SECURITY_HYGIENE not in floor.per_category


def test_n_runs_reflects_actual_not_requested_count() -> None:
    """A campaign that requested 3 but landed 2 records 2.

    Failed runs persist nothing, so a short series is what a lost run looks
    like — and the floor must state the evidence it really rests on.
    """
    floor = reduce_noise_floor(_runs_of_size([40, 44]))
    assert floor.n_runs == 2


def test_single_run_series_is_refused() -> None:
    with pytest.raises(AuditVarianceError, match="at least"):
        reduce_noise_floor(_runs_of_size([40]))


def test_empty_series_is_refused() -> None:
    with pytest.raises(AuditVarianceError):
        reduce_noise_floor([])


def test_mismatched_commit_sha_is_refused_and_names_the_field() -> None:
    """A floor measured across a code change is not a floor."""
    runs = [
        _run_with(run_id="audit-1", categories=[AuditCategory.TEST_DEBT]),
        _run_with(
            run_id="audit-2",
            categories=[AuditCategory.TEST_DEBT],
            commit_sha="c" * 40,
        ),
    ]

    with pytest.raises(AuditVarianceError, match="commit_sha"):
        reduce_noise_floor(runs)


def test_mismatched_prompt_hash_is_refused_and_names_the_field() -> None:
    """An instrument edit invalidates comparison across the edit."""
    runs = [
        _run_with(run_id="audit-1", categories=[AuditCategory.TEST_DEBT]),
        _run_with(
            run_id="audit-2",
            categories=[AuditCategory.TEST_DEBT],
            audit_prompt_hash="d" * 64,
        ),
    ]

    with pytest.raises(AuditVarianceError, match="audit_prompt_hash"):
        reduce_noise_floor(runs)


def test_multiple_projects_are_refused() -> None:
    """The floor is per-project and never pools across repos."""
    runs = [
        _run_with(run_id="audit-1", categories=[AuditCategory.TEST_DEBT]),
        _run_with(
            run_id="audit-2",
            categories=[AuditCategory.TEST_DEBT],
            project_value="github.com/manta/other-repo",
        ),
    ]

    with pytest.raises(AuditVarianceError, match="per-project"):
        reduce_noise_floor(runs)


def test_identical_runs_yield_a_zero_width_floor() -> None:
    """A genuinely stable audit reports zero spread — a real result.

    Distinct from the refused single-run case: two runs that agree is
    evidence of stability, whereas one run is no evidence at all.
    """
    floor = reduce_noise_floor(_runs_of_size([12, 12]))

    assert floor.total.min == floor.total.max == 12
    assert floor.total.stddev == pytest.approx(0.0)
