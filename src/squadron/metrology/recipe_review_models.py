"""The ``recipe_review`` record: one per recipe review executed (slice 434, D8).

Reuses 430's stage payload types (``StageKind``, ``StageConfig``, ``RecallFinding``,
``CombDecision``, ``StageUsage``, ``StageOutcome``) and adds no enum. ``StageEntry`` is not
reused whole: it needs a case set and a leak verdict, which a real review has neither of.
Raw stage output is in the ``REVIEWS`` content sidecar, keyed by ``raw_ref``.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict

from squadron.core.finding_categories import ReviewCategory
from squadron.core.models import Effort
from squadron.metrology.project_id import ProjectId
from squadron.metrology.recall_run_models import (
    CombDecision,
    RecallFinding,
    StageConfig,
    StageKind,
    StageOutcome,
    StageUsage,
)
from squadron.review.models import Verdict

#: Every recipe review record id starts with this.
RECIPE_REVIEW_ID_PREFIX = "rrev-"


class RecipeStage(BaseModel):
    """One stage that ran, in execution order; stages that did not run are absent."""

    model_config = ConfigDict(frozen=True)

    kind: StageKind
    #: The alias heading the chain.
    reviewer: str
    alias: str
    config: StageConfig
    #: The effort the provider applied; ``None`` when it applied none, never the configured one.
    effort_sent: Effort | None
    #: Review stages: every finding. Comb stages: the findings the comb was given.
    findings: list[RecallFinding] = []
    #: Comb stages: the decision per reviewer finding id.
    decisions: dict[str, CombDecision] = {}
    duplicate_decisions: int = 0
    unknown_ids: int = 0
    usage: StageUsage
    outcome: StageOutcome
    outcome_reason: str | None = None
    #: sha256 of the raw output in the ``REVIEWS`` sidecar; ``None`` when no call was made.
    raw_ref: str | None = None

    @property
    def made_call(self) -> bool:
        """A call reported something: it returned (raw output stored), or the provider error
        carried spend. A failure that reported nothing spent nothing."""
        return self.raw_ref is not None or self.usage != StageUsage()


class RecipeReview(BaseModel):
    """A recipe review: its plan, its stages, and the merged verdict."""

    model_config = ConfigDict(frozen=True)

    record_id: str
    project_id: ProjectId
    recipe: str
    recipe_hash: str
    template: str
    template_hash: str
    #: Pipeline linkage; all ``None`` from ``sq review`` (including prompt-only pipelines).
    run_id: str | None = None
    step_name: str | None = None
    iteration: int | None = None
    #: The saved review file; ``None`` when not saved.
    review_file: str | None = None
    #: Every stage the recipe defines, resolved before the first call (the report row key).
    planned: list[StageConfig]
    stages: list[RecipeStage]
    verdict: Verdict
    complete: bool
    #: Why the recipe did not finish (an unexpected error or a cancellation), else ``None``.
    aborted: str | None = None
    #: The category filter the review ran with (437 D6); ``None`` for a recipe with none.
    #: Which findings were gating derives from this and the stages' findings.
    keep_categories: tuple[ReviewCategory, ...] | None = None
    created: datetime


def new_recipe_review_id(clock: Callable[[], datetime] | None = None) -> str:
    """``rrev-<UTC timestamp>-<8 hex>``."""
    now = (clock or (lambda: datetime.now(UTC)))()
    stamp = now.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{RECIPE_REVIEW_ID_PREFIX}{stamp}-{uuid.uuid4().hex[:8]}"
