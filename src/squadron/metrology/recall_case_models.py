"""Real-bug recall case and case-set records (slice 430 D1, D10, D14).

A ``RealBugCase`` is content-addressed: ``case_id`` is ``rbcase-<sha12>`` of a canonical
projection of the identity fields, and a validator rejects a stored id that does not match,
so a hand-edited record fails on read instead of posing as the old case.
"""

from __future__ import annotations

import hashlib
import json
import posixpath
from datetime import datetime
from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from squadron.metrology.project_id import ProjectId

RECALL_CASE_ID_PREFIX = "rbcase-"
RECALL_CASE_SET_ID_PREFIX = "rbset-"
RECALL_ID_HEX_DIGITS = 12


class RecallCaseKind(StrEnum):
    """The case kind; ``kinds.py`` keys its registry on it (D14)."""

    CODE = "code"


class CaseStatus(StrEnum):
    VERIFIED = "verified"
    CHECKED = "checked"


class OriginalReview(StrEnum):
    """Whether the case's own saved review reported the bug."""

    MISSED = "missed"
    REPORTED = "reported"


class BugLocation(BaseModel):
    """A file a finding may cite for a bug; ``reason`` is required on hand-added locations."""

    model_config = ConfigDict(frozen=True)

    file: str
    symbol: str | None = None
    reason: str | None = None


class KnownBug(BaseModel):
    """One proven bug. ``locations`` is the resolved list: proof-commit files, then extras."""

    model_config = ConfigDict(frozen=True)

    id: str
    description: str
    proof: tuple[str, ...]
    original_review: OriginalReview
    locations: tuple[BugLocation, ...]
    extra_locations: tuple[BugLocation, ...] = ()

    @field_validator("extra_locations")
    @classmethod
    def _extras_have_reasons(cls, value: tuple[BugLocation, ...]) -> tuple[BugLocation, ...]:
        missing = [loc.file for loc in value if not (loc.reason and loc.reason.strip())]
        if missing:
            raise ValueError(f"extra location(s) without a reason: {missing}")
        return value


def _location_json(location: BugLocation) -> list[str | None]:
    return [location.file, location.symbol, location.reason]


def _bug_json(bug: KnownBug) -> dict[str, Any]:
    return {
        "id": bug.id,
        "description": bug.description,
        "proof": list(bug.proof),
        "original_review": bug.original_review.value,
        "locations": [_location_json(loc) for loc in bug.locations],
        "extra_locations": [_location_json(loc) for loc in bug.extra_locations],
    }


def compute_recall_case_id(
    *, kind: RecallCaseKind, repo: str, base: str, head: str, host_repo: str, bugs: tuple[KnownBug, ...]
) -> str:
    """``rbcase-<sha12>`` of canonical JSON of the identity fields (D1).

    Only the repo path's basename enters, so the same repo under another parent folder
    gives the same id. Bugs are sorted by id.
    """
    payload = {
        "kind": kind.value,
        "repo": posixpath.basename(repo.rstrip("/")),
        "base": base,
        "head": head,
        "host_repo": host_repo,
        "bugs": [_bug_json(bug) for bug in sorted(bugs, key=lambda b: b.id)],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"{RECALL_CASE_ID_PREFIX}{digest[:RECALL_ID_HEX_DIGITS]}"


class RealBugCase(BaseModel):
    """A real merged diff (``base..head``) with the bugs a later fix proved real."""

    model_config = ConfigDict(frozen=True)

    project_id: ProjectId
    case_id: str
    name: str
    kind: RecallCaseKind
    repo: str
    host_repo: str
    distribution: str
    base: str
    head: str
    status: CaseStatus
    hand_run_id: str | None = None
    bugs: tuple[KnownBug, ...]
    notes: str | None = None

    @model_validator(mode="after")
    def _id_matches_content(self) -> Self:
        expected = case_id_for(self)
        if self.case_id != expected:
            raise ValueError(f"case_id {self.case_id} does not match its content (expected {expected})")
        return self

    @classmethod
    def build(cls, **fields: Any) -> Self:
        """Construct a case with its derived ``case_id``."""
        case_id = compute_recall_case_id(
            kind=RecallCaseKind(fields["kind"]),
            repo=fields["repo"],
            base=fields["base"],
            head=fields["head"],
            host_repo=fields["host_repo"],
            bugs=tuple(fields["bugs"]),
        )
        return cls(case_id=case_id, **fields)


def case_id_for(case: RealBugCase) -> str:
    """The content-derived id of *case*."""
    return compute_recall_case_id(
        kind=case.kind,
        repo=case.repo,
        base=case.base,
        head=case.head,
        host_repo=case.host_repo,
        bugs=case.bugs,
    )


class RecallCaseSet(BaseModel):
    """One version of a named list of recall cases."""

    model_config = ConfigDict(frozen=True)

    name: str
    version: int
    case_ids: tuple[str, ...]
    created: datetime

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
        return case_set_id(self.name, self.version)

    @property
    def ref(self) -> str:
        """``<name>@v<version>``, the benchmark id paired seeds use (D12)."""
        return f"{self.name}@v{self.version}"


def case_set_id(name: str, version: int) -> str:
    """``rbset-<name>-v<version>``."""
    return f"{RECALL_CASE_SET_ID_PREFIX}{name}-v{version}"
