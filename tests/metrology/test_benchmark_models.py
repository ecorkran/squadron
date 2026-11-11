"""BenchmarkCase identity and CaseSet validation (slice 421 D1, D2)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from squadron.benchmark.adapter import EnvironmentIdentity
from squadron.metrology.benchmark_models import (
    BenchmarkCase,
    CandidateRejection,
    CaseKind,
    CaseProvenance,
    CaseSet,
    ConftestFixture,
    FixQualification,
    GraderCommand,
    GraderCommandKind,
    HiddenTestVerdict,
    HiddenTestVerdictKind,
    QualificationOutcome,
    TestRejection,
    case_set_record_id,
    fix_qualification_record_id,
)
from squadron.metrology.project_id import ProjectId, ProjectIdSource
from squadron.metrology.snapshot_models import SourceLanguage

NOW = datetime(2026, 11, 6, tzinfo=UTC)


def provenance(ref: str = "issue-1") -> CaseProvenance:
    return CaseProvenance(source_ref=ref, created_at=NOW, built_by="test")


def base_fields() -> dict[str, Any]:
    return {
        "project_id": ProjectId(value="proj", source=ProjectIdSource.RECORDED),
        "kind": CaseKind.FIX,
        "start_sha": "a" * 40,
        "reference_sha": "b" * 40,
        "task_text": "fix it",
        "hidden_tests": ("t/a.py::one", "t/a.py::two"),
        "hidden_fixtures": (ConftestFixture(conftest_path="conftest.py", fixture_name="f"),),
        "superseded_tests": ("t/old.py::x",),
        "excluded_tests": ("t/flaky.py::y",),
        "grader_commands": (GraderCommand(kind=GraderCommandKind.SUITE, argv=("pytest", "-q")),),
        "provenance": provenance(),
    }


def build(**overrides: Any) -> BenchmarkCase:
    return BenchmarkCase.build(**{**base_fields(), **overrides})


CHANGES: dict[str, Any] = {
    "project_id": ProjectId(value="other", source=ProjectIdSource.RECORDED),
    "kind": CaseKind.SLICE,
    "start_sha": "c" * 40,
    "reference_sha": "d" * 40,
    "task_text": "different",
    "hidden_tests": ("t/a.py::one",),
    "hidden_fixtures": (ConftestFixture(conftest_path="conftest.py", fixture_name="g"),),
    "superseded_tests": (),
    "excluded_tests": ("t/flaky.py::z",),
    "grader_commands": (GraderCommand(kind=GraderCommandKind.LINT, argv=("ruff",)),),
}


@pytest.mark.parametrize("field", sorted(CHANGES))
def test_each_identity_field_changes_the_case_id(field: str) -> None:
    assert build(**{field: CHANGES[field]}).case_id != build().case_id


def test_case_id_shape() -> None:
    case_id = build().case_id
    assert case_id.startswith("case-")
    assert len(case_id) == len("case-") + 16


def test_provenance_does_not_change_the_id() -> None:
    assert build(provenance=provenance("issue-2")).case_id == build().case_id


def test_list_order_does_not_matter() -> None:
    reordered = build(hidden_tests=("t/a.py::two", "t/a.py::one"))
    assert reordered.case_id == build().case_id


def test_json_round_trip_equals_original() -> None:
    case = build()
    assert BenchmarkCase.model_validate_json(case.model_dump_json()) == case


def test_wrong_stored_case_id_fails_validation() -> None:
    data = build().model_dump()
    data["case_id"] = "case-0000000000000000"
    with pytest.raises(ValidationError, match="does not match"):
        BenchmarkCase.model_validate(data)


def test_case_set_rejects_bad_slug_version_and_duplicates() -> None:
    with pytest.raises(ValidationError, match="slug"):
        CaseSet(name="Bad Name", version=1, case_ids=(), created_at=NOW)
    with pytest.raises(ValidationError, match="version"):
        CaseSet(name="ok", version=0, case_ids=(), created_at=NOW)
    with pytest.raises(ValidationError, match="duplicates"):
        CaseSet(name="ok", version=1, case_ids=("a", "a"), created_at=NOW)


def test_case_set_sorts_ids_and_derives_record_id() -> None:
    case_set = CaseSet(name="ok", version=2, case_ids=("b", "a"), created_at=NOW)
    assert case_set.case_ids == ("a", "b")
    assert case_set.record_id == case_set_record_id("ok", 2)
    assert case_set.record_id.startswith("caseset-")
    assert case_set.record_id.endswith("-v2")


# --- Fix qualification records (slice 422 D8, D10) ---

PROJECT = ProjectId(value="proj", source=ProjectIdSource.RECORDED)


def environment(lock_hash: str = "l" * 64) -> EnvironmentIdentity:
    return EnvironmentIdentity(
        language=SourceLanguage.PYTHON,
        lockfile_path="uv.lock",
        lockfile_sha256=lock_hash,
        interpreter_version="3.12.1",
        installer_version="uv 0.5",
        platform="darwin-arm64",
        scrub_spec_version=1,
    )


def qualification(**overrides: Any) -> FixQualification:
    fields: dict[str, Any] = {
        "project_id": PROJECT,
        "commit_sha": "c" * 40,
        "parent_sha": "d" * 40,
        "issue_ref": "o/r#1",
        "rule_version": 1,
        "environment": environment(),
        "repeats": 3,
        "outcome": QualificationOutcome.QUALIFIED,
        "case_id": "case-0123456789abcdef",
        "hidden_verdicts": (
            HiddenTestVerdict(node_id="t.py::a", kind=HiddenTestVerdictKind.QUALIFIED),
            HiddenTestVerdict(
                node_id="t.py::b",
                kind=HiddenTestVerdictKind.REJECTED,
                rejection=TestRejection.PATCHES_PROJECT_CODE,
                detail="fixpkg.mod.run",
            ),
        ),
        "excluded_with_reasons": (("t.py::flaky", TestRejection.FLAKY),),
        "created_at": NOW,
    }
    return FixQualification(**{**fields, **overrides})


def test_candidate_rejection_values_match_the_design() -> None:
    assert {member.value for member in CandidateRejection} == {
        "merge_commit",
        "root_commit",
        "multiple_closing_commits",
        "multiple_issues_closed",
        "no_issue_host",
        "issue_not_found",
        "reference_is_pull_request",
        "issue_edited_after_fix",
        "no_fix_case_adapter",
        "no_test_change",
        "test_data_changed",
        "modifies_test_support",
        "changes_lockfile",
        "environment_unresolved",
        "collection_failed",
        "no_packaging_boundary",
        "boundary_undecidable",
        "no_qualifying_hidden_test",
    }


def test_test_rejection_values_match_the_design() -> None:
    assert {member.value for member in TestRejection} == {
        "passes_at_parent",
        "uses_symbol_added_by_fix",
        "undecidable_failure_at_parent",
        "reaches_past_boundary",
        "patches_project_code",
        "boundary_undecidable",
        "flaky",
        "fails_at_reference",
    }


def test_outcome_and_verdict_kind_values_match_the_design() -> None:
    assert {member.value for member in QualificationOutcome} == {
        "qualified",
        "rejected",
        "harness_error",
    }
    assert {member.value for member in HiddenTestVerdictKind} == {"qualified", "rejected"}


@pytest.mark.parametrize(
    "overrides",
    [
        {"outcome": QualificationOutcome.QUALIFIED, "case_id": None},
        {"rejection": CandidateRejection.NO_TEST_CHANGE},
        {"outcome": QualificationOutcome.REJECTED, "case_id": None},
        {
            "outcome": QualificationOutcome.REJECTED,
            "rejection": CandidateRejection.NO_TEST_CHANGE,
        },
        {"outcome": QualificationOutcome.HARNESS_ERROR},
        {
            "outcome": QualificationOutcome.HARNESS_ERROR,
            "case_id": None,
            "rejection": CandidateRejection.NO_TEST_CHANGE,
        },
    ],
)
def test_qualification_rejects_bad_outcome_combinations(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        qualification(**overrides)


def test_qualification_accepts_each_valid_combination() -> None:
    qualification()
    qualification(
        outcome=QualificationOutcome.REJECTED,
        case_id=None,
        rejection=CandidateRejection.NO_QUALIFYING_HIDDEN_TEST,
    )
    qualification(outcome=QualificationOutcome.HARNESS_ERROR, case_id=None)


def test_hidden_verdict_rejects_bad_kind_rejection_pairs() -> None:
    with pytest.raises(ValidationError, match="needs a rejection"):
        HiddenTestVerdict(node_id="t.py::a", kind=HiddenTestVerdictKind.REJECTED)
    with pytest.raises(ValidationError, match="cannot carry"):
        HiddenTestVerdict(
            node_id="t.py::a",
            kind=HiddenTestVerdictKind.QUALIFIED,
            rejection=TestRejection.FLAKY,
        )


def test_qualification_json_round_trip_equals_original() -> None:
    record = qualification()
    assert FixQualification.model_validate_json(record.model_dump_json()) == record
    pre = qualification(
        environment=None,
        outcome=QualificationOutcome.REJECTED,
        case_id=None,
        rejection=CandidateRejection.NO_TEST_CHANGE,
        hidden_verdicts=(),
        excluded_with_reasons=(),
    )
    assert FixQualification.model_validate_json(pre.model_dump_json()) == pre


def test_record_id_uses_pre_without_an_environment() -> None:
    record_id = fix_qualification_record_id(PROJECT, "c" * 40, None)
    assert record_id.endswith(f"-{'c' * 12}-pre")
    assert record_id.startswith("fixqual-")


def test_record_id_uses_the_environment_digest_prefix() -> None:
    env = environment()
    record_id = fix_qualification_record_id(PROJECT, "c" * 40, env.identity_digest)
    assert record_id.endswith(f"-{'c' * 12}-{env.identity_digest[:12]}")
    assert qualification().record_id == record_id


def test_record_id_differs_per_project_and_environment() -> None:
    other = ProjectId(value="other", source=ProjectIdSource.RECORDED)
    sha = "c" * 40
    digest = environment().identity_digest
    assert fix_qualification_record_id(PROJECT, sha, digest) != fix_qualification_record_id(
        other, sha, digest
    )
    assert fix_qualification_record_id(PROJECT, sha, digest) != fix_qualification_record_id(
        PROJECT, sha, environment("m" * 64).identity_digest
    )
