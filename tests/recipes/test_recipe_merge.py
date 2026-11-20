"""One merged review from a recipe's stages (slice 434, D5, D6)."""

from __future__ import annotations

from pathlib import Path

from squadron.recipes.recipe import Recipe
from squadron.recipes.recipe_merge import (
    INCOMPLETE_FAIL_NOTE,
    INCOMPLETE_UNKNOWN_NOTE,
    RECIPE_SECTION_HEADING,
    merge_recipe,
)
from squadron.review.models import ReviewResult, Severity, Verdict
from tests.recipes.support import (
    Scripted,
    ScriptedReviewCall,
    decisions_text,
    provider_error,
    review_finding,
    review_result,
    run_scripted,
)

A1, A2 = review_finding("a1"), review_finding("a2-dropped")
A_NOTE = review_finding("a-note", Severity.NOTE)
B1 = review_finding("b1", Severity.FAIL)


def comb(*pairs: tuple[str, str]) -> Scripted:
    return review_result([], Verdict.PASS, raw=decisions_text(*pairs), cost=0.002)


def _script(**overrides: list[Scripted]) -> dict[str, list[Scripted]]:
    script: dict[str, list[Scripted]] = {
        "rev-a": [review_result([A1, A2, A_NOTE])],
        "rev-b": [review_result([B1], Verdict.FAIL)],
        "comb-1": [comb(("F1", "KEEP"), ("F2", "DROP")), comb(("F1", "KEEP"))],
        "comb-2": [comb(("F1", "KEEP")), comb(("F1", "KEEP"))],
    }
    script.update(overrides)
    return script


def _merge(recipe: Recipe, tmp_path: Path, **overrides: list[Scripted]) -> ReviewResult:
    outcome = run_scripted(recipe, ScriptedReviewCall(_script(**overrides)), tmp_path)
    return merge_recipe(outcome, recipe.name, "code", {"diff": "HEAD~1"})


def test_order_marks_and_renumbering(recipe: Recipe, tmp_path: Path) -> None:
    result = _merge(recipe, tmp_path)
    assert [f.title for f in result.findings] == ["a1", "b1", "a-note"]
    assert result.findings[0].description.endswith("Reviewer: rev-a")
    assert result.findings[1].description.endswith("Reviewer: rev-b")
    assert [sf.id for sf in result.structured_findings] == ["F001", "F002", "F003"]
    assert result.verdict is Verdict.FAIL
    assert result.recipe is not None and result.recipe.complete


def test_pass_when_every_concern_was_dropped_although_reviewers_stated_concerns(
    recipe: Recipe, tmp_path: Path
) -> None:
    result = _merge(
        recipe,
        tmp_path,
        **{
            "rev-b": [review_result([review_finding("b-concern")])],
            "comb-1": [comb(("F1", "DROP"), ("F2", "DROP")), comb(("F1", "DROP"))],
        },
    )
    assert result.verdict is Verdict.PASS
    assert [f.title for f in result.findings] == ["a-note"]


def test_incomplete_with_nothing_kept_is_unknown(recipe: Recipe, tmp_path: Path) -> None:
    result = _merge(
        recipe,
        tmp_path,
        **{"rev-a": [provider_error()], "comb-1": [comb(("F1", "DROP"))]},
    )
    assert result.verdict is Verdict.UNKNOWN
    assert result.recipe is not None and not result.recipe.complete
    assert INCOMPLETE_UNKNOWN_NOTE in result.recipe.stage_section


def test_incomplete_with_concern_kept_is_fail_with_the_section_line(
    recipe: Recipe, tmp_path: Path
) -> None:
    result = _merge(recipe, tmp_path, **{"rev-b": [provider_error("quota")]})
    assert [f.title for f in result.findings] == ["a1", "a-note"]
    assert result.verdict is Verdict.FAIL
    assert result.recipe is not None
    assert INCOMPLETE_FAIL_NOTE in result.recipe.stage_section
    assert "- Failed stage review rev-b: quota" in result.recipe.stage_section


def test_all_reviewers_failed_is_unknown(recipe: Recipe, tmp_path: Path) -> None:
    result = _merge(recipe, tmp_path, **{"rev-a": [provider_error()], "rev-b": [provider_error()]})
    assert result.verdict is Verdict.UNKNOWN and result.findings == []


def test_not_combed_mark(recipe: Recipe, tmp_path: Path) -> None:
    result = _merge(recipe, tmp_path, **{"comb-1": [provider_error(), comb(("F1", "KEEP"))]})
    marked = [f for f in result.findings if "not combed: comb-1 failed" in f.description]
    # Both passed through the failed comb-1; comb-2 kept F1 and left F2 undecided (kept).
    assert [f.title for f in marked] == ["a1", "a2-dropped"]
    assert result.verdict is Verdict.FAIL


def test_sums_and_no_dropped_finding_anywhere(recipe: Recipe, tmp_path: Path) -> None:
    result = _merge(recipe, tmp_path)
    assert result.cost_usd is not None
    assert round(result.cost_usd, 6) == round(0.01 * 2 + 0.002 * 4, 6)
    assert result.duration_seconds == 12.0 and result.turns == 6 and result.tool_calls_made == 18
    assert "a2-dropped" not in result.raw_output
    assert all("a2-dropped" not in f.title for f in result.findings)
    assert result.recipe is not None
    assert result.raw_output.count(RECIPE_SECTION_HEADING) == 1
    assert len(result.recipe.stage_section.splitlines()) > 6


def test_to_dict_keys_match_a_single_model_result(recipe: Recipe, tmp_path: Path) -> None:
    result = _merge(recipe, tmp_path)
    single = review_result([A1])
    assert set(result.to_dict()) == set(single.to_dict())
