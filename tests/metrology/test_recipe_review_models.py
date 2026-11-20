"""The ``recipe_review`` record payload (slice 434, D8)."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from squadron.metrology.models import RECORD_TYPE_RECIPE_REVIEW, MetrologyRecord
from squadron.metrology.project_id import ProjectId, ProjectIdSource
from squadron.metrology.recall_run_models import (
    CombDecision,
    CombVerdict,
    StageConfig,
    StageKind,
    StageOutcome,
    StageUsage,
)
from squadron.metrology.recipe_review_models import (
    RecipeReview,
    RecipeStage,
    new_recipe_review_id,
)
from squadron.review.models import Verdict

NOW = datetime(2026, 11, 19, 12, 30, 5, tzinfo=UTC)
CONFIG = StageConfig(
    model="m", profile="openrouter", template_hash="h", tool_use=True, max_output_tokens=None
)


def _record() -> RecipeReview:
    stage = RecipeStage(
        kind=StageKind.COMB,
        reviewer="rev-a",
        alias="comb-1",
        config=CONFIG,
        effort_sent=None,
        decisions={"F1": CombDecision(verdict=CombVerdict.KEEP, reason="real")},
        duplicate_decisions=1,
        usage=StageUsage(cost_usd=0.01),
        outcome=StageOutcome.OK,
        raw_ref="a" * 64,
    )
    return RecipeReview(
        record_id=new_recipe_review_id(lambda: NOW),
        project_id=ProjectId(value="github.com/x/y", source=ProjectIdSource.REMOTE),
        recipe="duo",
        recipe_hash="r" * 64,
        template="code",
        template_hash="h",
        planned=[CONFIG],
        stages=[stage],
        verdict=Verdict.FAIL,
        complete=True,
        created=NOW,
    )


def test_round_trip_through_the_envelope() -> None:
    record = _record()
    envelope = MetrologyRecord(
        schema_version=1, record_type=RECORD_TYPE_RECIPE_REVIEW, recipe_review=record
    )
    loaded = MetrologyRecord.model_validate_json(envelope.model_dump_json())
    assert loaded.recipe_review == record


def test_null_linkage_and_effort_survive() -> None:
    dumped = _record().model_dump(mode="json")
    assert dumped["run_id"] is None and dumped["step_name"] is None
    assert dumped["iteration"] is None and dumped["review_file"] is None
    assert dumped["stages"][0]["effort_sent"] is None
    assert RecipeReview.model_validate(dumped).stages[0].effort_sent is None


def test_id_format() -> None:
    record_id = new_recipe_review_id(lambda: NOW)
    assert re.fullmatch(r"rrev-20261119T123005Z-[0-9a-f]{8}", record_id)
    assert new_recipe_review_id(lambda: NOW) != record_id
