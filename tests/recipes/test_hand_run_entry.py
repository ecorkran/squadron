"""The hand-run line-pass entry, reproduced from stored reviewer outputs (slice 437, D11).

The fixtures are the ``findings`` and verdict of five benchmark PRs' stored ``haiku-xhigh``
and ``haiku`` line-pass outputs (``20261122-martian/out``). ``expected.json`` lists, per PR and
reviewer, the titles the hand-run entry sent: written once by the rule in that directory's
``convert.py`` (severity CONCERN or FAIL, category in the five), not by the code under test.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict, cast

import pytest

from squadron.core.finding_categories import ReviewCategory
from squadron.models import aliases
from squadron.recipes.recipe import Recipe, load_recipe
from squadron.recipes.recipe_merge import merge_recipe
from squadron.recipes.recipe_search import shipped_recipes_dir
from squadron.review.models import ReviewFinding, ReviewResult, Severity, Verdict
from tests.recipes.support import Scripted, ScriptedReviewCall, review_result, run_scripted

FIXTURES = Path(__file__).parent / "fixtures" / "hand_run"
EXPECTED: dict[str, dict[str, list[str]]] = json.loads(
    (FIXTURES / "expected.json").read_text(encoding="utf-8")
)
REVIEWERS = ("haiku-xhigh", "haiku")
RECIPE_NAME = "haiku-line-pass"
GATING_SEVERITIES = (Severity.CONCERN, Severity.FAIL)


@pytest.fixture(autouse=True)
def built_in_aliases_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(aliases, "load_user_aliases", lambda: {})


class StoredFinding(TypedDict):
    severity: str
    title: str
    description: str
    location: str | None
    category: str | None


class StoredReview(TypedDict):
    verdict: str
    findings: list[StoredFinding]


def _stored(case: str, alias: str) -> StoredReview:
    text = (FIXTURES / f"{case}-{alias}.json").read_text(encoding="utf-8")
    return cast(StoredReview, json.loads(text))


def _finding(entry: StoredFinding) -> ReviewFinding:
    return ReviewFinding(
        severity=Severity(entry["severity"]),
        title=entry["title"],
        description=entry["description"],
        location=entry["location"],
        category=entry["category"],
    )


def _result(case: str, alias: str) -> ReviewResult:
    stored = _stored(case, alias)
    findings = [_finding(entry) for entry in stored["findings"]]
    return review_result(findings, Verdict(stored["verdict"]))


def _merged(case: str, recipe: Recipe, cwd: Path) -> ReviewResult:
    script: dict[str, list[Scripted]] = {alias: [_result(case, alias)] for alias in REVIEWERS}
    outcome = run_scripted(recipe, ScriptedReviewCall(script), cwd)
    return merge_recipe(outcome, recipe.name, "code", {"diff": "HEAD~1"})


def _titles(result: ReviewResult, alias: str) -> list[str]:
    mark = f"Reviewer: {alias}"
    return [
        f.title
        for f in result.findings
        if f.severity in GATING_SEVERITIES and f.description.endswith(mark)
    ]


@pytest.mark.parametrize("case", sorted(EXPECTED))
def test_gating_titles_equal_the_hand_run_entry(case: str, tmp_path: Path) -> None:
    recipe = load_recipe(shipped_recipes_dir() / f"{RECIPE_NAME}.yaml")
    result = _merged(case, recipe, tmp_path)
    for alias in REVIEWERS:
        assert _titles(result, alias) == EXPECTED[case][alias], f"{case} {alias}"
    # The test is only meaningful if the filter removed something and kept something.
    assert result.recipe is not None and result.recipe.not_gating > 0


def test_every_fixture_category_is_a_review_category_value() -> None:
    valid = {category.value for category in ReviewCategory}
    found = {
        entry["category"]
        for case in EXPECTED
        for alias in REVIEWERS
        for entry in _stored(case, alias)["findings"]
        if entry["category"] is not None
    }
    assert found <= valid
    assert ReviewCategory.OTHER.value in found  # at least one PR has a finding in other


def test_every_concern_and_fail_fixture_finding_has_a_category() -> None:
    uncategorized = [
        (case, alias, entry["title"])
        for case in EXPECTED
        for alias in REVIEWERS
        for entry in _stored(case, alias)["findings"]
        if entry["severity"] in ("CONCERN", "FAIL") and not entry["category"]
    ]
    assert uncategorized == []
