"""The ``slice_ranges`` record: where each slice landed on the target (slice 403, D1).

One record per project holds every slice's landings, oldest first. A landing is
never changed once stored; a later resolution only adds landings it didn't have,
matched on ``after_sha``. The record sits behind the metrology envelope as an
optional sibling payload, so ``schema_version`` does not move.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, model_validator

from squadron.metrology.project_id import ProjectId


class LandingMethod(StrEnum):
    """How a slice reached the target."""

    MERGE_COMMIT = "merge_commit"
    FAST_FORWARD = "fast_forward"


class RangeUnresolvedReason(StrEnum):
    """Why a slice has no landing. Git answered each of these except ``GIT_ERROR``."""

    NO_LANDING = "no_landing"
    NOT_LANDED = "not_landed"
    LANDED_ELSEWHERE = "landed_elsewhere"
    REFLOG_UNAVAILABLE = "reflog_unavailable"
    EMPTY_BRANCH = "empty_branch"
    FORK_NOT_ANCESTOR = "fork_not_ancestor"
    GIT_ERROR = "git_error"


class SliceLanding(BaseModel):
    """One landing of a slice on the target.

    ``before_sha`` and ``after_sha`` are the target just before and just after
    the landing (D3). ``merge_sha`` is the merge commit, ``None`` for a fast-forward.
    """

    method: LandingMethod
    target_ref: str
    before_sha: str
    after_sha: str
    fork_sha: str
    tip_sha: str
    merge_sha: str | None
    resolved_at: datetime


class SliceRanges(BaseModel):
    """Every resolved slice's landings for one project."""

    record_id: str
    project_id: ProjectId
    #: Each list is non-empty, oldest first, with unique ``after_sha``.
    slices: dict[int, list[SliceLanding]]

    @model_validator(mode="after")
    def _check_landings(self) -> SliceRanges:
        for index, landings in self.slices.items():
            self._check_slice(index, landings)
        return self

    @staticmethod
    def _check_slice(index: int, landings: list[SliceLanding]) -> None:
        if not landings:
            raise ValueError(f"slice {index}: landings must not be empty")
        seen: set[str] = set()
        for landing in landings:
            if landing.after_sha in seen:
                raise ValueError(f"slice {index}: duplicate after_sha {landing.after_sha}")
            seen.add(landing.after_sha)
            is_merge = landing.method is LandingMethod.MERGE_COMMIT
            if is_merge and landing.merge_sha is None:
                raise ValueError(f"slice {index}: merge_sha is required for a merge_commit landing")
            if not is_merge and landing.merge_sha is not None:
                raise ValueError(f"slice {index}: merge_sha must be None for a fast_forward landing")
