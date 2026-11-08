"""Benchmark case and case-set records (slice 421 D1, D2).

A ``BenchmarkCase`` is content-addressed: ``case_id`` is derived from the ten identity
fields and a validator rejects a stored id that does not match, so a hand-edited file fails
on read instead of becoming a second case under the old id. Provenance is stored but is not
part of the identity.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from squadron.metrology.benchmark_environment import EnvironmentIdentity
from squadron.metrology.project_id import ProjectId

CASE_ID_PREFIX = "case-"
CASE_ID_HEX_DIGITS = 16
CASE_SET_ID_PREFIX = "caseset-"
CASE_SET_NAME_HASH_DIGITS = 12
_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


class CaseKind(StrEnum):
    FIX = "fix"
    SLICE = "slice"


class GraderCommandKind(StrEnum):
    SUITE = "suite"
    LINT = "lint"
    TYPECHECK = "typecheck"


class ConftestFixture(BaseModel):
    model_config = ConfigDict(frozen=True)

    conftest_path: str
    fixture_name: str


class GraderCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: GraderCommandKind
    argv: tuple[str, ...]


class CaseProvenance(BaseModel):
    """Where a case came from; never part of its identity."""

    model_config = ConfigDict(frozen=True)

    source_ref: str
    created_at: datetime
    built_by: str


IDENTITY_FIELDS = (
    "project_id",
    "kind",
    "start_sha",
    "reference_sha",
    "task_text",
    "hidden_tests",
    "hidden_fixtures",
    "superseded_tests",
    "excluded_tests",
    "grader_commands",
)


def _canonical_identity(
    *,
    project_id: ProjectId,
    kind: CaseKind,
    start_sha: str,
    reference_sha: str,
    task_text: str,
    hidden_tests: tuple[str, ...],
    hidden_fixtures: tuple[ConftestFixture, ...],
    superseded_tests: tuple[str, ...],
    excluded_tests: tuple[str, ...],
    grader_commands: tuple[GraderCommand, ...],
) -> str:
    """Canonical JSON (sorted keys, no whitespace) of the identity fields, lists sorted."""
    payload: dict[str, Any] = {
        "project_id": project_id.value,
        "kind": kind.value,
        "start_sha": start_sha,
        "reference_sha": reference_sha,
        "task_text": task_text,
        "hidden_tests": sorted(hidden_tests),
        "hidden_fixtures": sorted(
            [fixture.conftest_path, fixture.fixture_name] for fixture in hidden_fixtures
        ),
        "superseded_tests": sorted(superseded_tests),
        "excluded_tests": sorted(excluded_tests),
        "grader_commands": sorted(
            [[command.kind.value, list(command.argv)] for command in grader_commands],
            key=lambda item: json.dumps(item),
        ),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def compute_case_id(**identity: Any) -> str:
    """``case-`` plus the first 16 hex digits of the sha256 of the canonical identity."""
    digest = hashlib.sha256(_canonical_identity(**identity).encode("utf-8")).hexdigest()
    return f"{CASE_ID_PREFIX}{digest[:CASE_ID_HEX_DIGITS]}"


class BenchmarkCase(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    project_id: ProjectId
    kind: CaseKind
    start_sha: str
    reference_sha: str
    task_text: str
    hidden_tests: tuple[str, ...]
    hidden_fixtures: tuple[ConftestFixture, ...]
    superseded_tests: tuple[str, ...]
    excluded_tests: tuple[str, ...]
    grader_commands: tuple[GraderCommand, ...]
    provenance: CaseProvenance

    def _identity_id(self) -> str:
        return compute_case_id(**{name: getattr(self, name) for name in IDENTITY_FIELDS})

    @model_validator(mode="after")
    def _id_matches_content(self) -> Self:
        expected = self._identity_id()
        if self.case_id != expected:
            raise ValueError(f"case_id {self.case_id} does not match its content (expected {expected})")
        return self

    @classmethod
    def build(
        cls,
        *,
        project_id: ProjectId,
        kind: CaseKind,
        start_sha: str,
        reference_sha: str,
        task_text: str,
        hidden_tests: tuple[str, ...],
        hidden_fixtures: tuple[ConftestFixture, ...],
        superseded_tests: tuple[str, ...],
        excluded_tests: tuple[str, ...],
        grader_commands: tuple[GraderCommand, ...],
        provenance: CaseProvenance,
    ) -> Self:
        """Construct a case with its derived ``case_id``."""
        fields: dict[str, Any] = {
            "project_id": project_id,
            "kind": kind,
            "start_sha": start_sha,
            "reference_sha": reference_sha,
            "task_text": task_text,
            "hidden_tests": hidden_tests,
            "hidden_fixtures": hidden_fixtures,
            "superseded_tests": superseded_tests,
            "excluded_tests": excluded_tests,
            "grader_commands": grader_commands,
            "provenance": provenance,
        }
        case_id = compute_case_id(**{name: fields[name] for name in IDENTITY_FIELDS})
        return cls(case_id=case_id, **fields)


class CaseSet(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    version: int
    case_ids: tuple[str, ...]
    created_at: datetime

    @field_validator("name")
    @classmethod
    def _name_is_slug(cls, value: str) -> str:
        if not _SLUG.fullmatch(value):
            raise ValueError(f"case set name '{value}' is not a lowercase slug")
        return value

    @field_validator("version")
    @classmethod
    def _version_positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError(f"case set version must be >= 1, got {value}")
        return value

    @field_validator("case_ids")
    @classmethod
    def _ids_sorted_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("case set case_ids contain duplicates")
        return tuple(sorted(value))

    @property
    def record_id(self) -> str:
        return case_set_record_id(self.name, self.version)


def case_set_record_id(name: str, version: int) -> str:
    """``caseset-<sha256(name)[:12]>-v<version>``."""
    digest = hashlib.sha256(name.encode("utf-8")).hexdigest()
    return f"{CASE_SET_ID_PREFIX}{digest[:CASE_SET_NAME_HASH_DIGITS]}-v{version}"


FIX_QUALIFICATION_ID_PREFIX = "fixqual-"
FIX_QUALIFICATION_HASH_DIGITS = 12
FIX_QUALIFICATION_NO_ENVIRONMENT = "pre"


class CandidateRejection(StrEnum):
    """Why a whole fix candidate is not a case (slice 422, Patterns and Conventions)."""

    MERGE_COMMIT = "merge_commit"
    MULTIPLE_CLOSING_COMMITS = "multiple_closing_commits"
    MULTIPLE_ISSUES_CLOSED = "multiple_issues_closed"
    NO_ISSUE_HOST = "no_issue_host"
    ISSUE_NOT_FOUND = "issue_not_found"
    REFERENCE_IS_PULL_REQUEST = "reference_is_pull_request"
    ISSUE_EDITED_AFTER_FIX = "issue_edited_after_fix"
    NO_FIX_CASE_ADAPTER = "no_fix_case_adapter"
    NO_TEST_CHANGE = "no_test_change"
    TEST_DATA_CHANGED = "test_data_changed"
    MODIFIES_TEST_SUPPORT = "modifies_test_support"
    CHANGES_LOCKFILE = "changes_lockfile"
    ENVIRONMENT_UNRESOLVED = "environment_unresolved"
    COLLECTION_FAILED = "collection_failed"
    NO_PACKAGING_BOUNDARY = "no_packaging_boundary"
    BOUNDARY_UNDECIDABLE = "boundary_undecidable"
    NO_QUALIFYING_HIDDEN_TEST = "no_qualifying_hidden_test"


class TestRejection(StrEnum):
    """Why one hidden test, or one ``excluded_tests`` entry, is not usable."""

    __test__ = False  # pytest: a class named Test* is not a test class

    PASSES_AT_PARENT = "passes_at_parent"
    USES_SYMBOL_ADDED_BY_FIX = "uses_symbol_added_by_fix"
    UNDECIDABLE_FAILURE_AT_PARENT = "undecidable_failure_at_parent"
    REACHES_PAST_BOUNDARY = "reaches_past_boundary"
    PATCHES_PROJECT_CODE = "patches_project_code"
    BOUNDARY_UNDECIDABLE = "boundary_undecidable"
    FLAKY = "flaky"
    FAILS_AT_REFERENCE = "fails_at_reference"


class QualificationOutcome(StrEnum):
    QUALIFIED = "qualified"
    REJECTED = "rejected"
    HARNESS_ERROR = "harness_error"


class HiddenTestVerdictKind(StrEnum):
    QUALIFIED = "qualified"
    REJECTED = "rejected"


class HiddenTestVerdict(BaseModel):
    """The result for one hidden candidate; ``detail`` names the symbol, target or runs."""

    model_config = ConfigDict(frozen=True)

    node_id: str
    kind: HiddenTestVerdictKind
    rejection: TestRejection | None = None
    detail: str = ""

    @model_validator(mode="after")
    def _rejection_matches_kind(self) -> Self:
        rejected = self.kind is HiddenTestVerdictKind.REJECTED
        if rejected and self.rejection is None:
            raise ValueError("a rejected verdict needs a rejection")
        if not rejected and self.rejection is not None:
            raise ValueError("a qualified verdict cannot carry a rejection")
        return self


def fix_qualification_record_id(project_id: ProjectId, commit_sha: str, env_digest: str | None) -> str:
    """``fixqual-<sha256(project_id)[:12]>-<commit[:12]>-<env digest[:12] or "pre">``."""
    project_hash = hashlib.sha256(project_id.value.encode("utf-8")).hexdigest()
    environment = (
        FIX_QUALIFICATION_NO_ENVIRONMENT
        if env_digest is None
        else env_digest[:FIX_QUALIFICATION_HASH_DIGITS]
    )
    return (
        f"{FIX_QUALIFICATION_ID_PREFIX}{project_hash[:FIX_QUALIFICATION_HASH_DIGITS]}"
        f"-{commit_sha[:FIX_QUALIFICATION_HASH_DIGITS]}-{environment}"
    )


class FixQualification(BaseModel):
    """One qualification result for a closing commit (slice 422 D10)."""

    model_config = ConfigDict(frozen=True)

    project_id: ProjectId
    commit_sha: str
    parent_sha: str
    issue_ref: str | None
    rule_version: int
    environment: EnvironmentIdentity | None
    repeats: int
    outcome: QualificationOutcome
    case_id: str | None = None
    rejection: CandidateRejection | None = None
    detail: str = ""
    hidden_verdicts: tuple[HiddenTestVerdict, ...] = ()
    excluded_with_reasons: tuple[tuple[str, TestRejection], ...] = ()
    created_at: datetime

    @model_validator(mode="after")
    def _outcome_matches_fields(self) -> Self:
        qualified = self.outcome is QualificationOutcome.QUALIFIED
        rejected = self.outcome is QualificationOutcome.REJECTED
        if qualified != (self.case_id is not None):
            raise ValueError("case_id is set exactly when the outcome is qualified")
        if rejected != (self.rejection is not None):
            raise ValueError("rejection is set exactly when the outcome is rejected")
        return self

    @property
    def record_id(self) -> str:
        digest = None if self.environment is None else self.environment.identity_digest
        return fix_qualification_record_id(self.project_id, self.commit_sha, digest)
