"""The recipe runner: stage order, kept findings, failures and the slow warning (434 D3-D5)."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import pytest

from squadron.core.models import Effort
from squadron.metrology.identity import template_behavior_hash
from squadron.metrology.recall_run_models import CombVerdict, StageKind, StageOutcome
from squadron.recipes.comb_call import COMB_ALLOWED_TOOLS, call_comb
from squadron.recipes.recipe import Recipe
from squadron.recipes.recipe_outcome import RecipeOutcome, RecipeProgress
from squadron.recipes.recipe_runner import RecipeReviewCall, run_recipe
from squadron.recipes.stage_config import builtin_template, plan_recipe, planned_stages
from squadron.review.models import Severity, Verdict
from tests.recipes.conftest import RECIPE_ALIASES
from tests.recipes.support import (
    Scripted,
    ScriptedReviewCall,
    decisions_text,
    provider_error,
    provider_error_with_spend,
    review_finding,
    review_result,
)

LOGGER = "squadron.recipes.recipe_runner"
CHANGED = ["src/app.py", "src/util.py"]
INPUTS = {"cwd": ".", "diff": "HEAD~1"}

A1, A2 = review_finding("a1"), review_finding("a2")
A_NOTE = review_finding("a-note", Severity.NOTE)
B1 = review_finding("b1", Severity.FAIL)


def comb(*pairs: tuple[str, str]) -> Scripted:
    return review_result([], Verdict.PASS, raw=decisions_text(*pairs))


def _script(**overrides: list[Scripted]) -> dict[str, list[Scripted]]:
    script: dict[str, list[Scripted]] = {
        "rev-a": [review_result([A1, A2, A_NOTE])],
        "rev-b": [review_result([B1], Verdict.FAIL)],
        # call 0 is rev-a's chain, call 1 is rev-b's
        "comb-1": [comb(("F1", "KEEP"), ("F2", "DROP")), comb(("F1", "KEEP"))],
        "comb-2": [comb(("F1", "KEEP")), comb(("F1", "KEEP"))],
    }
    script.update(overrides)
    return script


def _run(
    recipe: Recipe,
    scripted: ScriptedReviewCall,
    tmp_path: Path,
    *,
    slow_after_s: float = 60,
    progress: RecipeProgress | None = None,
) -> RecipeOutcome:
    call = RecipeReviewCall(
        template=builtin_template("code"),
        inputs=INPUTS,
        options={"allowed_tools": ["read_file"], "rules_content": "rules"},
        review_call=scripted,
        comb_call=call_comb,
    )
    return asyncio.run(
        run_recipe(
            recipe,
            call=call,
            plan=plan_recipe(recipe, call.template),
            changed_files=CHANGED,
            cwd=tmp_path,
            slow_after_s=slow_after_s,
            progress=progress if progress is not None else RecipeProgress(),
        )
    )


def _warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING and r.name == LOGGER]


def test_stage_order_and_call_inputs(recipe: Recipe, tmp_path: Path) -> None:
    scripted = ScriptedReviewCall(_script())
    outcome = _run(recipe, scripted, tmp_path)
    assert scripted.aliases() == ["rev-a", "comb-1", "comb-2", "rev-b", "comb-1", "comb-2"]
    for record in scripted.calls:
        if record.alias.startswith("comb"):
            assert record.template == "comb"
            assert record.allowed_tools == list(COMB_ALLOWED_TOOLS)
            assert record.inputs["changed_files"] == "\n".join(CHANGED)
            assert record.cwd == str(tmp_path)
        else:
            assert record.template == "code"
            assert record.inputs == INPUTS
            assert record.allowed_tools == ["read_file"]
    assert outcome.complete


def test_planned_and_kept_findings(recipe: Recipe, tmp_path: Path) -> None:
    outcome = _run(recipe, ScriptedReviewCall(_script()), tmp_path)
    template = builtin_template("code")
    assert list(outcome.planned) == planned_stages(recipe, template_behavior_hash(template))
    rev_a, rev_b = outcome.reviewers
    assert [f.title for f in rev_a.kept] == ["a1"]  # a2 dropped by comb-1
    assert [f.title for f in rev_a.uncombed] == ["a-note"]
    assert [f.title for f in rev_b.kept] == ["b1"]
    comb_1 = outcome.stages[1]
    assert comb_1.decisions["F2"].verdict is CombVerdict.DROP


def test_empty_comb_input_makes_no_call(recipe: Recipe, tmp_path: Path) -> None:
    script = _script(**{"rev-a": [review_result([A_NOTE], Verdict.PASS)]})
    scripted = ScriptedReviewCall(script)
    outcome = _run(recipe, scripted, tmp_path)
    assert scripted.aliases() == ["rev-a", "rev-b", "comb-1", "comb-2"]
    empty = [s for s in outcome.stages if s.reviewer == "rev-a" and s.kind is StageKind.COMB]
    assert [s.outcome for s in empty] == [StageOutcome.OK, StageOutcome.OK]
    assert all(s.result is None and not s.decisions for s in empty)


def test_effort_sent_is_the_results_effort_never_the_alias_config(
    recipe: Recipe, tmp_path: Path
) -> None:
    script = _script(**{"rev-b": [review_result([B1], Verdict.FAIL, effort=Effort.low)]})
    outcome = _run(recipe, ScriptedReviewCall(script), tmp_path)
    by_alias = {s.alias: s for s in outcome.stages if s.kind is StageKind.REVIEW}
    assert RECIPE_ALIASES["rev-a"].get("effort") is Effort.high  # configured, never sent here
    assert by_alias["rev-a"].effort_sent is None
    assert by_alias["rev-b"].effort_sent is Effort.low


# --- D5 failed stages -------------------------------------------------------------


def test_reviewer_provider_error_is_harness_failure_and_skips_its_combs(
    recipe: Recipe, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    scripted = ScriptedReviewCall(_script(**{"rev-a": [provider_error("quota exceeded")]}))
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        outcome = _run(recipe, scripted, tmp_path)
    assert scripted.aliases() == ["rev-a", "rev-b", "comb-1", "comb-2"]
    failed = outcome.stages[0]
    assert failed.outcome is StageOutcome.HARNESS_FAILURE and failed.reason == "quota exceeded"
    assert outcome.reviewers[0].kept == () and not outcome.complete
    assert any(
        "recipe duo" in w and "review rev-a" in w and "quota exceeded" in w for w in _warnings(caplog)
    )


def test_reviewer_unknown_verdict_is_config_failure_and_findings_unused(
    recipe: Recipe, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    scripted = ScriptedReviewCall(_script(**{"rev-a": [review_result([A1], Verdict.UNKNOWN)]}))
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        outcome = _run(recipe, scripted, tmp_path)
    assert outcome.stages[0].outcome is StageOutcome.CONFIG_FAILURE
    assert outcome.reviewers[0].kept == () and not outcome.complete
    assert "comb-1" not in scripted.aliases()[:2]
    assert any("review rev-a" in w and "UNKNOWN" in w for w in _warnings(caplog))


@pytest.mark.parametrize(
    ("first_comb", "outcome_kind"),
    [
        (provider_error("comb down"), StageOutcome.HARNESS_FAILURE),
        (comb(), StageOutcome.CONFIG_FAILURE),  # no parseable decision line
    ],
)
def test_failed_comb_passes_input_on_uncombed(
    recipe: Recipe,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    first_comb: Scripted,
    outcome_kind: StageOutcome,
) -> None:
    script = _script(**{"comb-1": [first_comb, comb(("F1", "KEEP"))]})
    scripted = ScriptedReviewCall(script)
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        outcome = _run(recipe, scripted, tmp_path)
    failed = outcome.stages[1]
    assert failed.outcome is outcome_kind and failed.not_combed == ("F1", "F2")
    second = scripted.calls[2]
    assert second.alias == "comb-2" and "F2" in second.inputs["findings"]  # both passed on
    rev_a = outcome.reviewers[0]
    assert rev_a.not_combed == {"F1": "comb-1", "F2": "comb-1"}
    assert not outcome.complete
    assert any("comb rev-a > comb-1" in w for w in _warnings(caplog))


def test_partial_decisions_are_undecided_and_kept(recipe: Recipe, tmp_path: Path) -> None:
    script = _script(**{"comb-1": [comb(("F1", "DROP")), comb(("F1", "KEEP"))]})
    scripted = ScriptedReviewCall(script)
    outcome = _run(recipe, scripted, tmp_path)
    comb_1 = outcome.stages[1]
    assert comb_1.outcome is StageOutcome.OK
    assert comb_1.decisions["F2"].verdict is CombVerdict.UNDECIDED
    assert [f.title for f in outcome.reviewers[0].kept] == ["a2"]
    assert scripted.aliases()[2] == "rev-b"  # nothing left for comb-2 on rev-a's chain
    assert outcome.complete


def test_repeated_and_unknown_ids_warn_with_both_counts(
    recipe: Recipe, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    noisy = comb(("F1", "KEEP"), ("F1", "DROP"), ("F2", "DROP"), ("F9", "KEEP"))
    script = _script(**{"comb-1": [noisy, comb(("F1", "KEEP"))]})
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        outcome = _run(recipe, ScriptedReviewCall(script), tmp_path)
    comb_1 = outcome.stages[1]
    assert comb_1.outcome is StageOutcome.OK
    assert (comb_1.duplicate_decisions, comb_1.unknown_ids) == (1, 1)
    assert comb_1.decisions["F1"].verdict is CombVerdict.KEEP  # first decision wins
    assert any("repeated 1 decision(s)" in w and "1 unknown id(s)" in w for w in _warnings(caplog))


def test_unexpected_exception_propagates_with_finished_stages_in_progress(
    recipe: Recipe, tmp_path: Path
) -> None:
    progress = RecipeProgress()
    scripted = ScriptedReviewCall(_script(**{"rev-b": [RuntimeError("parse bug")]}))
    with pytest.raises(RuntimeError, match="parse bug"):
        _run(recipe, scripted, tmp_path, progress=progress)
    assert [s.alias for s in progress.stages] == ["rev-a", "comb-1", "comb-2"]


def test_slow_stage_logs_one_warning_and_finishes(
    recipe: Recipe, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    single = Recipe(name="solo", reviewers=("rev-a",))
    scripted = ScriptedReviewCall(_script(), delay_s=0.2)
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        outcome = _run(single, scripted, tmp_path, slow_after_s=0.05)
    (warning,) = _warnings(caplog)
    assert "recipe solo" in warning and "review rev-a" in warning and "still running after" in warning
    assert outcome.complete and len(outcome.stages) == 1


def test_failed_stage_keeps_the_spend_its_error_reported(recipe: Recipe, tmp_path: Path) -> None:
    script = _script(**{"rev-a": [provider_error_with_spend(cost=0.03, prompt_tokens=500)]})
    outcome = _run(recipe, ScriptedReviewCall(script), tmp_path)
    failed = outcome.stages[0]
    assert failed.outcome is StageOutcome.HARNESS_FAILURE and failed.made_call
    assert (failed.usage.cost_usd, failed.usage.turns, failed.usage.duration_s) == (0.03, 2, 4.0)
    assert failed.tokens.prompt == 500


def test_failed_stage_that_reported_nothing_spent_nothing(recipe: Recipe, tmp_path: Path) -> None:
    outcome = _run(recipe, ScriptedReviewCall(_script(**{"rev-a": [provider_error()]})), tmp_path)
    assert not outcome.stages[0].made_call
