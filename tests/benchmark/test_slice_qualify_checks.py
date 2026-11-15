"""Reuse lookup, ``can_skip`` and the pre-sandbox checks (slice 426, Task 15)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

import pytest

from squadron.benchmark.slice_qualify import (
    SLICE_RULE_VERSION,
    can_skip,
    qualify_slice_candidate,
    slice_qualification_for,
)
from squadron.core.process_runner import ProcessResult
from squadron.metrology.benchmark_models import (
    BenchmarkCase,
    CaseKind,
    CaseProvenance,
    QualificationOutcome,
)
from squadron.metrology.benchmark_store import BenchmarkRecordStore
from squadron.metrology.slice_case_models import SliceCandidateRejection, SliceQualification
from squadron.metrology.slice_case_store import SliceCaseRecordStore
from squadron.metrology.store import MetrologyStore
from tests.benchmark.slice_case_support import CREATED, LANDING, PROJECT, environment, qualification
from tests.benchmark.slice_qualify_support import typical_setup
from tests.benchmark.slice_repos import (
    docs_only_slice,
    no_design_at_fork,
    no_slice_plan_at_fork,
    no_task_file_at_fork,
    two_parent_landing,
)

DIGEST = environment().identity_digest


def _case(index: int = 403, after_sha: str = LANDING) -> BenchmarkCase:
    return BenchmarkCase.build(
        project_id=PROJECT,
        kind=CaseKind.SLICE,
        start_sha="f" * 40,
        reference_sha="a" * 40,
        task_text="task",
        hidden_tests=(),
        hidden_fixtures=(),
        superseded_tests=(),
        excluded_tests=(),
        grader_commands=(),
        provenance=CaseProvenance(
            source_ref=f"slice:{index}@{after_sha}", created_at=CREATED, built_by="test"
        ),
    )


REPEATS = 3  # the repeat count the support module's records carry


@pytest.fixture
def store(tmp_path: Path) -> SliceCaseRecordStore:
    return SliceCaseRecordStore(BenchmarkRecordStore(MetrologyStore(store_dir=tmp_path / "store")))


def test_a_matching_record_is_returned(store: SliceCaseRecordStore) -> None:
    record = qualification(start_environment=environment())
    store.write_slice_qualification(record)

    assert slice_qualification_for(store, _case(), environment(), REPEATS) == record


def test_another_digest_landing_or_rule_version_returns_none(store: SliceCaseRecordStore) -> None:
    store.write_slice_qualification(qualification(start_environment=environment()))
    store.write_slice_qualification(
        qualification(start_environment=environment("9" * 64), rule_version=SLICE_RULE_VERSION + 1)
    )

    assert slice_qualification_for(store, _case(), environment("8" * 64), REPEATS) is None
    assert slice_qualification_for(store, _case(after_sha="c" * 40), environment(), REPEATS) is None
    assert slice_qualification_for(store, _case(), environment("9" * 64), REPEATS) is None


def test_a_record_made_under_another_repeat_count_is_not_reused(
    store: SliceCaseRecordStore,
) -> None:
    store.write_slice_qualification(qualification(start_environment=environment()))

    assert slice_qualification_for(store, _case(), environment(), REPEATS + 1) is None


def test_a_case_that_is_not_a_slice_case_is_an_error(store: SliceCaseRecordStore) -> None:
    odd = _case().model_copy(
        update={"provenance": CaseProvenance(source_ref="issue#12", created_at=CREATED, built_by="t")}
    )

    with pytest.raises(ValueError, match="not a slice case"):
        slice_qualification_for(store, odd, environment(), REPEATS)


def test_can_skip_rules() -> None:
    keyed = qualification(start_environment=environment())
    pre = qualification(QualificationOutcome.REJECTED, rejection=SliceCandidateRejection.NO_CODE_CHANGE)
    harness = qualification(QualificationOutcome.HARNESS_ERROR)
    old = qualification(start_environment=environment(), rule_version=SLICE_RULE_VERSION + 1)

    assert can_skip(pre, None, REPEATS)  # a pre-sandbox record needs no digest
    assert can_skip(keyed, DIGEST, REPEATS)
    assert not can_skip(keyed, "0" * 64, REPEATS)
    assert not can_skip(keyed, None, REPEATS)
    assert not can_skip(harness, None, REPEATS)
    assert not can_skip(old, DIGEST, REPEATS)
    # The flaky and always-failing exclusions depend on the repeat count.
    assert not can_skip(keyed, DIGEST, REPEATS + 1)
    assert can_skip(pre, None, REPEATS + 1)  # no suite ran, so the count does not matter


class _GitMustNotRun:
    def run(self, argv: Sequence[str], **kwargs: object) -> ProcessResult:
        raise AssertionError(f"git ran: {argv}")


def test_a_stored_pre_sandbox_rejection_is_returned_without_building_a_sandbox(
    tmp_path: Path,
) -> None:
    setup = typical_setup(tmp_path / "s", docs_only_slice(tmp_path / "repo"))
    first = qualify_slice_candidate(setup.candidate, setup.deps)

    again = qualify_slice_candidate(setup.candidate, replace(setup.deps, runner=_GitMustNotRun()))

    assert again.reused
    assert again.record == first.record
    assert setup.factory.built == []
    assert again.record.rejection is SliceCandidateRejection.NO_CODE_CHANGE


@pytest.mark.parametrize(
    ("build", "rejection"),
    [
        (no_design_at_fork, SliceCandidateRejection.NO_DESIGN_AT_FORK),
        (no_task_file_at_fork, SliceCandidateRejection.NO_TASKS_AT_FORK),
        (no_slice_plan_at_fork, SliceCandidateRejection.NO_SLICE_PLAN_AT_FORK),
        (docs_only_slice, SliceCandidateRejection.NO_CODE_CHANGE),
    ],
)
def test_each_pre_sandbox_check_rejects_before_any_sandbox(
    tmp_path: Path, build: object, rejection: SliceCandidateRejection
) -> None:
    setup = typical_setup(tmp_path / "s", build(tmp_path / "repo"))  # type: ignore[operator]

    result = qualify_slice_candidate(setup.candidate, setup.deps)

    assert result.record.outcome is QualificationOutcome.REJECTED
    assert result.record.rejection is rejection
    assert result.record.start_environment is None
    assert setup.factory.built == []
    stored = setup.qualifications.get_slice_qualification(
        PROJECT, setup.candidate.slice_index, setup.candidate.landing.after_sha, None
    )
    assert isinstance(stored, SliceQualification) and stored == result.record
    assert result.case is None


def test_a_slice_that_passes_the_checks_writes_no_pre_sandbox_record(tmp_path: Path) -> None:
    setup = typical_setup(tmp_path / "s", two_parent_landing(tmp_path / "repo"))

    qualify_slice_candidate(setup.candidate, setup.deps)

    assert (
        setup.qualifications.get_slice_qualification(
            PROJECT, setup.candidate.slice_index, setup.candidate.landing.after_sha, None
        )
        is None
    )
