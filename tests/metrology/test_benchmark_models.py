"""BenchmarkCase identity and CaseSet validation (slice 421 D1, D2)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from squadron.metrology.benchmark_models import (
    BenchmarkCase,
    CaseKind,
    CaseProvenance,
    CaseSet,
    ConftestFixture,
    GraderCommand,
    GraderCommandKind,
    case_set_record_id,
)
from squadron.metrology.project_id import ProjectId, ProjectIdSource

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
