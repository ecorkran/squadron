"""A scripted ``haiku-line-pass`` review through the review action (slice 437).

Shared by the action's recipe tests and the reviser's findings test, so both read the same
scripted outputs: ``haiku-xhigh`` raises one gating and one not-gating CONCERN, ``haiku`` (the
no-tools line pass) one gating FAIL and one finding in ``other``.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from squadron.core.finding_categories import ReviewCategory
from squadron.metrology.project_id import ProjectId, ProjectIdSource
from squadron.models import aliases
from squadron.pipeline.actions.review import ReviewAction
from squadron.pipeline.models import ActionContext, ActionResult
from squadron.pipeline.resolver import ModelResolver
from squadron.pipeline.usage_capture import UsageCapture
from squadron.recipes import recipe_review
from squadron.review.models import Severity, Verdict
from tests.recipes.conftest import RECIPE_ALIASES
from tests.recipes.support import (
    FakeRecipeSink,
    Scripted,
    ScriptedReviewCall,
    defect_repo,
    review_finding,
    review_result,
)

LINE_PASS = "haiku-line-pass"
STEP_RULES = "Project rule: prefer early returns."
PROJECT = ProjectId(value="github.com/x/fixture", source=ProjectIdSource.REMOTE)
X_GATE = review_finding("x-gate", Severity.CONCERN, ReviewCategory.CORRECTNESS.value)
X_DEBT = review_finding("x-debt", Severity.CONCERN, ReviewCategory.TEST_DEBT.value)
H_GATE = review_finding("h-gate", Severity.FAIL, ReviewCategory.CORRECTNESS.value)
H_OTHER = review_finding("h-other", Severity.CONCERN, ReviewCategory.OTHER.value)
NOT_GATING_TITLES = ("x-debt", "h-other")


def line_pass_script(**overrides: list[Scripted]) -> dict[str, list[Scripted]]:
    script: dict[str, list[Scripted]] = {
        "haiku-xhigh": [review_result([X_GATE, X_DEBT])],
        "haiku": [review_result([H_GATE, H_OTHER], Verdict.FAIL)],
    }
    script.update(overrides)
    return script


def prepare_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A defect repo; the shipped recipe is found by the production search."""
    monkeypatch.setattr(aliases, "load_user_aliases", lambda: dict(RECIPE_ALIASES))
    monkeypatch.setattr(recipe_review, "derive_project_id", lambda cwd: PROJECT)
    return defect_repo(tmp_path / "repo")


def line_pass_context(repo: Path, sink: FakeRecipeSink) -> ActionContext:
    return ActionContext(
        pipeline_name="p",
        run_id="run-1",
        params={
            "template": "code",
            "diff": "HEAD~1",
            "model": LINE_PASS,
            "rules_content": STEP_RULES,
        },
        step_name="review",
        step_index=0,
        prior_outputs={},
        resolver=ModelResolver(),
        cf_client=MagicMock(),
        cwd=str(repo),
        usage_capture=UsageCapture(set()),
        recipe_sink=sink,
    )


async def run_line_pass_review(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    sink: FakeRecipeSink,
    **overrides: list[Scripted],
) -> tuple[ActionResult, ScriptedReviewCall]:
    scripted = ScriptedReviewCall(line_pass_script(**overrides))
    monkeypatch.setattr(recipe_review, "run_review_with_profile", scripted)
    result = await ReviewAction().execute(line_pass_context(repo, sink))
    return result, scripted
