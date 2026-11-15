"""Grading enums, grader identity and review models (slice 425 D10, D16, Patterns).

``GradeAbsence``, ``GradeSubject`` and ``PairVerdict`` are the only definitions of their
values; reports group by the enum, never by message text. ``ReviewerRef.reviewer_key`` and
``GraderIdentity.digest`` are derived and validated on read, as ``BenchmarkCase.case_id``
is, so a hand-edited record fails instead of becoming a second identity.
"""

from __future__ import annotations

import hashlib
import json
import re
from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from squadron.metrology.benchmark_nodes import NodeResult
from squadron.metrology.benchmark_replay_enums import AbsenceClass
from squadron.metrology.review_models import CodeReviewFinding

_SHA256 = re.compile(r"[0-9a-f]{64}")

#: Every listing a grade record keeps is cut to this many entries, with its true count
#: beside it, so a record stays under the store bound (D2, Database Schema).
MAX_LISTED_ITEMS = 50
#: A grade record's free-text ``detail`` is cut to this many characters.
DETAIL_MAX_CHARS = 1000


class GradeSubject(StrEnum):
    REFERENCE = "reference"
    REPLAY = "replay"


class GradeAbsence(StrEnum):
    """Why a grade has no result (D16); the values are the table's first column."""

    PRODUCER_ENV_UNRESOLVABLE = "producer_env_unresolvable"
    ENVIRONMENT_FAILED = "environment_failed"
    ENVIRONMENT_CHANGED = "environment_changed"
    DIFF_APPLY_FAILED = "diff_apply_failed"
    GRADER_TIMEOUT = "grader_timeout"
    SUITE_ERROR = "suite_error"
    REVIEW_FAILED = "review_failed"
    CHECK_TOOL_MISMATCH = "check_tool_mismatch"
    SNAPSHOT_FAILED = "snapshot_failed"
    REFERENCE_UNREADABLE = "reference_unreadable"
    REFERENCE_FAILED_GRADE = "reference_failed_grade"


class PairVerdict(StrEnum):
    A_AHEAD = "a_ahead"
    B_AHEAD = "b_ahead"
    NOT_DISTINGUISHABLE = "not_distinguishable"
    TOO_FEW_CASES = "too_few_cases"


#: D16's third column. Only a producer's own unresolvable tree is the config's fault;
#: every other absence is the harness's and drops the case from every config.
GRADE_ABSENCE_CLASS: dict[GradeAbsence, AbsenceClass] = {
    absence: (
        AbsenceClass.CONFIG
        if absence is GradeAbsence.PRODUCER_ENV_UNRESOLVABLE
        else AbsenceClass.HARNESS
    )
    for absence in GradeAbsence
}


def sha256_of_canonical_json(payload: dict[str, Any]) -> str:
    """sha256 hex of *payload* as JSON with sorted keys and no whitespace."""
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ReviewerRef(BaseModel):
    """The grading reviewer: an alias resolved to model, profile, effort and template.

    No rules hash: the rules directory is the start commit's and differs per case, while the
    grader identity is one value per benchmark (D7, D10). ``alias`` is a label and is not
    part of ``reviewer_key``.
    """

    model_config = ConfigDict(frozen=True)

    alias: str
    model: str
    profile: str
    effort: str | None
    template_hash: str
    reviewer_key: str

    @staticmethod
    def derive_key(model: str, profile: str, effort: str | None, template_hash: str) -> str:
        return sha256_of_canonical_json(
            {"model": model, "profile": profile, "effort": effort, "template_hash": template_hash}
        )

    @classmethod
    def build(
        cls,
        *,
        alias: str,
        model: str,
        profile: str,
        effort: str | None,
        template_hash: str,
    ) -> Self:
        key = cls.derive_key(model, profile, effort, template_hash)
        return cls(
            alias=alias,
            model=model,
            profile=profile,
            effort=effort,
            template_hash=template_hash,
            reviewer_key=key,
        )

    @model_validator(mode="after")
    def _key_matches_content(self) -> Self:
        expected = self.derive_key(self.model, self.profile, self.effort, self.template_hash)
        if self.reviewer_key != expected:
            raise ValueError(f"reviewer_key does not match its content (expected {expected})")
        return self


#: Bumped whenever any grading step changes: a new version is a new grader identity (D10).
#: 2: the grading review shows producer edits to *.toml, *.yaml and *.yml (#335).
GRADER_VERSION = 2


class GraderIdentity(BaseModel):
    """One value for a whole benchmark: grader version, reviewer and floor runs (D10).

    The digest covers the reviewer through its ``reviewer_key``, so renaming an alias does
    not make a new identity but changing the model, profile, effort or template does.
    """

    model_config = ConfigDict(frozen=True)

    grader_version: int
    reviewer: ReviewerRef
    review_floor_runs: int
    digest: str

    @staticmethod
    def derive_digest(grader_version: int, reviewer: ReviewerRef, review_floor_runs: int) -> str:
        return sha256_of_canonical_json(
            {
                "grader_version": grader_version,
                "reviewer_key": reviewer.reviewer_key,
                "review_floor_runs": review_floor_runs,
            }
        )

    @classmethod
    def build(cls, *, grader_version: int, reviewer: ReviewerRef, review_floor_runs: int) -> Self:
        digest = cls.derive_digest(grader_version, reviewer, review_floor_runs)
        return cls(
            grader_version=grader_version,
            reviewer=reviewer,
            review_floor_runs=review_floor_runs,
            digest=digest,
        )

    @model_validator(mode="after")
    def _digest_matches_content(self) -> Self:
        expected = self.derive_digest(self.grader_version, self.reviewer, self.review_floor_runs)
        if self.digest != expected:
            raise ValueError(f"digest does not match its content (expected {expected})")
        return self


class SnapshotRef(BaseModel):
    """A content-addressed pointer to a stored snapshot sidecar (D11)."""

    model_config = ConfigDict(frozen=True)

    sha256: str

    @field_validator("sha256")
    @classmethod
    def _is_digest(cls, value: str) -> str:
        if not _SHA256.fullmatch(value):
            raise ValueError(f"{value!r} is not a sha256 hex digest")
        return value


class SuppressionCounts(BaseModel):
    """Suppressions added in ``start..HEAD`` (D6): ``noqa`` and ``type_ignore`` by file side."""

    model_config = ConfigDict(frozen=True)

    noqa_source: int = 0
    noqa_test: int = 0
    type_ignore_source: int = 0
    type_ignore_test: int = 0


class ReviewOutcome(BaseModel):
    """What one grading review returned (D7)."""

    model_config = ConfigDict(frozen=True)

    findings: tuple[CodeReviewFinding, ...]
    unnormalized_count: int
    cost_usd: float | None
    #: sha256 of the rules the reviewed tree supplied; ``None`` when it had none.
    rules_hash: str | None


class ReviewSummary(BaseModel):
    """What a grade record keeps of one review; the findings are a ``reviews`` sidecar."""

    model_config = ConfigDict(frozen=True)

    severity_counts: dict[str, int]
    total: int
    unnormalized_count: int
    cost_usd: float | None
    rules_hash: str | None
    findings_sha256: str

    @classmethod
    def from_outcome(cls, outcome: ReviewOutcome, findings_sha256: str) -> Self:
        counts: dict[str, int] = {}
        for finding in outcome.findings:
            counts[finding.severity.value] = counts.get(finding.severity.value, 0) + 1
        return cls(
            severity_counts=counts,
            total=len(outcome.findings),
            unnormalized_count=outcome.unnormalized_count,
            cost_usd=outcome.cost_usd,
            rules_hash=outcome.rules_hash,
            findings_sha256=findings_sha256,
        )


def check_detail(detail: str | None) -> str | None:
    """Return *detail* unchanged, or raise when it is longer than ``DETAIL_MAX_CHARS``."""
    if detail is not None and len(detail) > DETAIL_MAX_CHARS:
        raise ValueError(f"detail is {len(detail)} characters; the cap is {DETAIL_MAX_CHARS}")
    return detail


def _check_listing(name: str, listed: tuple[object, ...], true_count: int) -> None:
    if len(listed) > MAX_LISTED_ITEMS:
        raise ValueError(f"{name} lists {len(listed)} entries; the cap is {MAX_LISTED_ITEMS}")
    if true_count < len(listed):
        raise ValueError(f"{name} count {true_count} is below its {len(listed)} listed entries")


class GradeResult(BaseModel):
    """The measurements of one graded subject (D1, D2, Database Schema).

    ``passed`` is a property over stored fields and is never stored itself. Every capped
    listing sits beside its true count.
    """

    model_config = ConfigDict(frozen=True)

    hidden_total: int
    hidden_passed: int
    #: Hidden nodes whose outcome is not ``passed``, cut to ``MAX_LISTED_ITEMS``; the true
    #: count is ``hidden_total - hidden_passed``.
    hidden_failures: tuple[NodeResult, ...]
    #: ``nodes`` sidecar holding the injected id map.
    hidden_id_map_sha256: str
    injection_clashes: tuple[str, ...]
    injection_clash_count: int
    regression_selected: int
    regression_failures: tuple[str, ...]
    regression_failure_count: int
    producer_new_passed: int
    producer_new_failed: int
    config_edits: tuple[str, ...]
    config_edit_count: int
    test_edits: tuple[str, ...]
    test_edit_count: int
    suppressions: SuppressionCounts
    reinstalled: bool
    #: sha256 of the producer's ``uv.lock``; ``None`` when its tree has none.
    lockfile_sha256: str | None
    snapshot: SnapshotRef
    lint_total: int | None
    type_total: int | None
    #: One review for a replay, ``review_floor_runs`` for a reference.
    reviews: tuple[ReviewSummary, ...]

    @property
    def passed(self) -> bool:
        """Every hidden test passed and no regression node failed (D2)."""
        return self.hidden_passed == self.hidden_total and self.regression_failure_count == 0

    @field_validator("hidden_id_map_sha256")
    @classmethod
    def _is_digest(cls, value: str) -> str:
        if not _SHA256.fullmatch(value):
            raise ValueError(f"{value!r} is not a sha256 hex digest")
        return value

    @model_validator(mode="after")
    def _listings_are_capped_and_consistent(self) -> Self:
        if not 0 <= self.hidden_passed <= self.hidden_total:
            raise ValueError("hidden_passed must be between 0 and hidden_total")
        _check_listing("hidden_failures", self.hidden_failures, self.hidden_total - self.hidden_passed)
        _check_listing("injection_clashes", self.injection_clashes, self.injection_clash_count)
        _check_listing("regression_failures", self.regression_failures, self.regression_failure_count)
        _check_listing("config_edits", self.config_edits, self.config_edit_count)
        _check_listing("test_edits", self.test_edits, self.test_edit_count)
        return self
