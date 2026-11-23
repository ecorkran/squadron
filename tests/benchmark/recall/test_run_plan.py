"""``run``'s refusals, bound and auth preflight (slice 430 D6, D9, D11)."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from squadron.benchmark.auth_check import AuthAnswer, AuthCheckResult
from squadron.benchmark.recall.leak_check import leak_judgeable
from squadron.benchmark.recall.refusal import RecallRefusal
from squadron.benchmark.recall.run_bound import (
    auth_preflight,
    build_run_bound,
    render_bound,
    require_review_timeout,
)
from squadron.benchmark.recall.run_plan import expand_pending
from squadron.benchmark.recall.stage_identity import live_stage_config
from squadron.core.process_runner import ProcessRunner
from squadron.metrology.recall_run_models import (
    LIVE_SOURCE,
    RecallRun,
    StageKind,
    StageUsage,
)
from squadron.providers.base import ProfileName
from squadron.recipes.recipe import Recipe, load_recipe
from squadron.recipes.recipe_search import shipped_recipes_dir
from tests.benchmark.recall.committed import SETS_FILE, committed_cases, parse_sets
from tests.benchmark.recall.scoring_support import make_case, review
from tests.benchmark.recall.stage_support import live_config_for, pending_for

CASE = make_case()
ALWAYS = lambda profile: True  # noqa: E731


def _pending(recipe: Recipe) -> list:  # type: ignore[type-arg]
    return pending_for(CASE, recipe)


def test_refuses_without_max_cost() -> None:
    with pytest.raises(RecallRefusal, match="--max-cost"):
        build_run_bound(_pending(Recipe(name="r", reviewers=("a",))), [], None, 0.01, None, ALWAYS)


@pytest.mark.parametrize("max_cost", [float("nan"), float("inf"), 0.0, -1.0])
def test_refuses_a_max_cost_that_is_not_finite_and_positive(max_cost: float) -> None:
    """NaN passed ``<= 0`` and disabled the cap (430 gate review)."""
    with pytest.raises(RecallRefusal, match="--max-cost"):
        build_run_bound(_pending(Recipe(name="r", reviewers=("a",))), [], max_cost, 0.01, None, ALWAYS)


@pytest.mark.parametrize("call_cost", [float("nan"), float("inf"), 0.0, -1.0])
def test_refuses_a_call_cost_that_is_not_finite_and_positive(call_cost: float) -> None:
    with pytest.raises(RecallRefusal, match="--call-cost"):
        build_run_bound(_pending(Recipe(name="r", reviewers=("a",))), [], 1.0, call_cost, None, ALWAYS)


def test_refuses_without_review_timeout() -> None:
    with pytest.raises(RecallRefusal, match="benchmark.review_timeout_s"):
        require_review_timeout(None)
    assert require_review_timeout(600) == 600.0


def test_refuses_without_call_cost_when_nothing_observed() -> None:
    with pytest.raises(RecallRefusal, match="--call-cost"):
        build_run_bound(_pending(Recipe(name="r", reviewers=("a",))), [], 1.0, None, None, ALWAYS)


def test_refuses_a_profile_that_cannot_be_leak_checked() -> None:
    with pytest.raises(RecallRefusal, match="cannot be leak-checked"):
        build_run_bound(
            _pending(Recipe(name="r", reviewers=("a",))), [], 1.0, 0.01, None, lambda p: False
        )


def test_bound_arithmetic_and_call_cost_label() -> None:
    bound = build_run_bound(
        _pending(Recipe(name="r", reviewers=("a", "b"), combs=("c",))), [], 1.0, 0.02, None, ALWAYS
    )
    assert len(bound.priced) == 4
    assert bound.bound_usd == pytest.approx(4 * 0.02 + 0.02)
    assert bound.label == "from --call-cost"
    text = render_bound(bound)
    assert "4 stages to run" in text and "→ at most $0.10 (from --call-cost), capped at $1.00" in text


def test_observed_cost_gives_estimate_label() -> None:
    config, effort = live_config_for("a", StageKind.REVIEW)
    seen = review("a", (), source=LIVE_SOURCE).model_copy(
        update={"config": config, "effort_configured": effort, "usage": StageUsage(cost_usd=0.30)}
    )
    runs = [RecallRun(case_id="other", run_index=1, reviews={seen.entry_key: seen})]
    bound = build_run_bound(
        _pending(Recipe(name="r", reviewers=("a", "b"))), runs, 1.0, 0.01, None, ALWAYS
    )
    assert bound.figures[config.config_key].observed and bound.largest == 0.30
    assert bound.bound_usd == pytest.approx(0.30 + 0.01 + 0.30)
    assert bound.label == "estimate"


def _auth(answer: AuthAnswer):  # type: ignore[no-untyped-def]
    def check(
        aliases: Sequence[str],
        runner: ProcessRunner,
        root: Path,
        env: Mapping[str, str],
        sq: str,
        timeout: float,
    ) -> list[AuthCheckResult]:
        return [AuthCheckResult(ProfileName.OPENROUTER, aliases[0], answer, 1, "login expired")]

    return check


def test_auth_failure_is_error_and_refusal(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.ERROR), pytest.raises(RecallRefusal, match="openrouter"):
        auth_preflight(["luna-r"], None, tmp_path, {}, "/opt/sq", 5.0, _auth(AuthAnswer.NO))  # type: ignore[arg-type]
    assert any(r.levelno == logging.ERROR and "openrouter" in r.getMessage() for r in caplog.records)
    rows = auth_preflight(["luna-r"], None, tmp_path, {}, "/opt/sq", 5.0, _auth(AuthAnswer.YES))  # type: ignore[arg-type]
    assert rows[0].answer is AuthAnswer.YES


def test_shipped_recipe_on_nonsquadron_cases_gives_bound_with_plan_billed_count() -> None:
    cases = committed_cases()
    members = parse_sets(SETS_FILE.read_text(encoding="utf-8"))["real-bugs-nonsquadron"]
    recipe = load_recipe(shipped_recipes_dir() / "haiku-sol-luna.yaml")
    pending = expand_pending([recipe], [cases[m] for m in members], [1], {}, live_stage_config)
    # 14 cases x 2 reviewers x (1 review + 1 comb stage, luna-r)
    assert len(pending) == 14 * 2 * 2
    with pytest.raises(RecallRefusal, match="--max-plan-calls"):
        build_run_bound(pending, [], 25.0, 0.5, None, leak_judgeable)
    bound = build_run_bound(pending, [], 25.0, 0.5, 14, leak_judgeable)
    assert bound.plan_billed_calls == 14  # the sol reviews (Codex)
    text = render_bound(bound)
    assert "plan-billed calls: 14, cap 14" in text
    assert "review sol (openai-oauth): 14 calls plan-billed" in text
    assert "capped at $25.00" in text


def test_a_recorded_zero_cost_is_not_a_figure() -> None:
    config, effort = live_config_for("a", StageKind.REVIEW)
    free = review("a", (), source=LIVE_SOURCE).model_copy(
        update={"config": config, "effort_configured": effort, "usage": StageUsage(cost_usd=0.0)}
    )
    runs = [RecallRun(case_id="other", run_index=1, reviews={free.entry_key: free})]
    pending = _pending(Recipe(name="r", reviewers=("a",)))
    with pytest.raises(RecallRefusal, match="--call-cost"):
        build_run_bound(pending, runs, 1.0, None, None, ALWAYS)
    bound = build_run_bound(pending, runs, 1.0, 0.02, None, ALWAYS)
    assert bound.largest == 0.02 and bound.label == "from --call-cost"
