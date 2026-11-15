"""The regression selection and the case (slice 426, Task 18)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from squadron.benchmark.slice_qualify import qualify_slice_candidate
from squadron.benchmark.slice_task import TaskText, task_text_at
from squadron.core.process_runner import SubprocessRunner
from squadron.metrology.benchmark_models import CaseKind, QualificationOutcome
from squadron.metrology.slice_case_models import SliceCandidateRejection
from tests.benchmark.slice_qualify_support import FAILING, typical_setup
from tests.benchmark.slice_repos import two_parent_landing


def test_an_empty_regression_selection_is_no_regression_signal(tmp_path: Path) -> None:
    every_test_fails = ({node: FAILING for node in ("t::u1", "t::u2", "t::u3", "t::u4")},)
    setup = typical_setup(
        tmp_path / "s", two_parent_landing(tmp_path / "repo"), suite_runs=every_test_fails
    )

    result = qualify_slice_candidate(setup.candidate, setup.deps)

    assert result.record.outcome is QualificationOutcome.REJECTED
    assert result.record.rejection is SliceCandidateRejection.NO_REGRESSION_SIGNAL
    assert result.case is None
    assert result.record.case_id is None
    assert setup.cases.list_cases(setup.deps.project_id) == []


def test_a_qualified_case_has_the_designs_fields(tmp_path: Path) -> None:
    built = two_parent_landing(tmp_path / "repo")
    setup = typical_setup(tmp_path / "s", built)
    expected_text = task_text_at(built.landing.fork, built.index, built.repo, SubprocessRunner(), 30.0)
    assert isinstance(expected_text, TaskText)

    result = qualify_slice_candidate(setup.candidate, setup.deps)

    case = result.case
    assert case is not None
    assert result.record.outcome is QualificationOutcome.QUALIFIED
    assert result.record.case_id == case.case_id
    assert (case.kind, case.start_sha, case.reference_sha) == (
        CaseKind.SLICE,
        built.landing.fork,
        built.landing.tip,
    )
    assert case.task_text == expected_text.text
    assert (case.hidden_tests, case.hidden_fixtures) == ((), ())
    assert case.provenance.source_ref == f"slice:{built.index}@{built.landing.after}"
    assert setup.cases.get_case(case.case_id) == case
    assert result.record.detail == "2 regression nodes, 2 superseded, 2 excluded"
    assert result.record.slice_name == expected_text.slice_name


def test_the_case_id_is_stable_and_ignores_the_landing_sha(tmp_path: Path) -> None:
    built = two_parent_landing(tmp_path / "repo")
    first = typical_setup(tmp_path / "a", built)
    other_landing = first.candidate.landing.model_copy(update={"after_sha": "e" * 40})
    second = typical_setup(tmp_path / "b", built)
    shifted = replace(second.candidate, landing=other_landing)

    one = qualify_slice_candidate(first.candidate, first.deps)
    two = qualify_slice_candidate(shifted, second.deps)

    assert one.case is not None and two.case is not None
    assert one.case.case_id == two.case.case_id
    assert one.case.provenance.source_ref != two.case.provenance.source_ref


def test_the_stored_qualification_carries_both_environments(tmp_path: Path) -> None:
    setup = typical_setup(tmp_path / "s", two_parent_landing(tmp_path / "repo"))

    result = qualify_slice_candidate(setup.candidate, setup.deps)

    stored = setup.qualifications.get_slice_qualification(
        setup.deps.project_id,
        setup.candidate.slice_index,
        setup.candidate.landing.after_sha,
        result.record.start_environment.identity_digest if result.record.start_environment else None,
    )
    assert stored == result.record
    assert stored.start_environment is not None and stored.reference_environment is not None
    assert stored.start_environment != stored.reference_environment
