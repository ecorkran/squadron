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


def _canonical_identity(
    *,
    project_id: str,
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
        "project_id": project_id,
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
        return compute_case_id(
            project_id=self.project_id.value,
            kind=self.kind,
            start_sha=self.start_sha,
            reference_sha=self.reference_sha,
            task_text=self.task_text,
            hidden_tests=self.hidden_tests,
            hidden_fixtures=self.hidden_fixtures,
            superseded_tests=self.superseded_tests,
            excluded_tests=self.excluded_tests,
            grader_commands=self.grader_commands,
        )

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
        case_id = compute_case_id(
            project_id=project_id.value,
            kind=kind,
            start_sha=start_sha,
            reference_sha=reference_sha,
            task_text=task_text,
            hidden_tests=hidden_tests,
            hidden_fixtures=hidden_fixtures,
            superseded_tests=superseded_tests,
            excluded_tests=excluded_tests,
            grader_commands=grader_commands,
        )
        return cls(
            case_id=case_id,
            project_id=project_id,
            kind=kind,
            start_sha=start_sha,
            reference_sha=reference_sha,
            task_text=task_text,
            hidden_tests=hidden_tests,
            hidden_fixtures=hidden_fixtures,
            superseded_tests=superseded_tests,
            excluded_tests=excluded_tests,
            grader_commands=grader_commands,
            provenance=provenance,
        )


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
