"""The review action's recipe path: usage, success, failures, loops and the cost cap (434)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock

import pytest

from squadron.config.keys import COST_CAP_KEY
from squadron.config.manager import set_config
from squadron.core.usage import CostBasis
from squadron.metrology.project_id import ProjectId, ProjectIdSource
from squadron.metrology.recall_run_models import StageOutcome
from squadron.metrology.recipe_review_models import RecipeReview
from squadron.models import aliases
from squadron.pipeline.actions.review import ReviewAction
from squadron.pipeline.actions.review_recipe import (
    RECIPE_METADATA_KEY,
    RecipePart,
    RecipePartAborted,
    recipe_usage_record,
    run_recipe_part,
)
from squadron.pipeline.executor import ExecutionStatus, PipelineResult, execute_pipeline
from squadron.pipeline.failure_kind import FAILURE_KIND_KEY, FailureKind
from squadron.pipeline.models import ActionContext, ActionResult, PipelineDefinition, StepConfig
from squadron.pipeline.resolver import ModelResolver
from squadron.pipeline.usage_capture import UsageCapture
from squadron.providers.base import USAGE_KEY
from squadron.recipes import recipe_review
from squadron.recipes.model_ref import RecipeRef
from squadron.recipes.recipe import load_recipe
from squadron.recipes.recipe_outcome import RecipeStageResult
from squadron.recipes.recipe_search import PROJECT_RECIPES_DIR
from squadron.recipes.stage_config import builtin_template
from squadron.review.models import ReviewResult, Severity, Verdict
from squadron.review.persistence import REVIEWS_DIR
from tests.recipes.conftest import RECIPE_ALIASES
from tests.recipes.support import (
    RECIPE_NAME,
    RECIPE_TEXT,
    FakeRecipeSink,
    Scripted,
    ScriptedReviewCall,
    decisions_text,
    defect_repo,
    provider_error,
    provider_error_with_spend,
    review_finding,
    review_result,
    run_scripted,
)

PROJECT = ProjectId(value="github.com/x/fixture", source=ProjectIdSource.REMOTE)
A1 = review_finding("a1")
B1 = review_finding("b1")
B_FAIL = review_finding("b-fail", Severity.FAIL)


def comb(*pairs: tuple[str, str], cost: float | None = 0.002) -> Scripted:
    return review_result([], Verdict.PASS, raw=decisions_text(*pairs), cost=cost)


def _script(**overrides: list[Scripted]) -> dict[str, list[Scripted]]:
    script: dict[str, list[Scripted]] = {
        "rev-a": [review_result([A1])],
        "rev-b": [review_result([B_FAIL], Verdict.FAIL)],
        "comb-1": [comb(("F1", "KEEP"))],
        "comb-2": [comb(("F1", "KEEP"))],
    }
    script.update(overrides)
    return script


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, patch_config_paths: dict[str, Path]) -> Path:
    monkeypatch.setattr(aliases, "load_user_aliases", lambda: dict(RECIPE_ALIASES))
    root = defect_repo(tmp_path / "repo")
    recipes = root / PROJECT_RECIPES_DIR
    recipes.mkdir(parents=True)
    (recipes / f"{RECIPE_NAME}.yaml").write_text(RECIPE_TEXT, encoding="utf-8")
    monkeypatch.setattr(recipe_review, "derive_project_id", lambda cwd: PROJECT)
    return root


def _scripted(monkeypatch: pytest.MonkeyPatch, **overrides: list[Scripted]) -> ScriptedReviewCall:
    scripted = ScriptedReviewCall(_script(**overrides))
    monkeypatch.setattr(recipe_review, "run_review_with_profile", scripted)
    return scripted


def _context(
    repo: Path, sink: FakeRecipeSink, resolver: ModelResolver | None = None, **params: object
) -> ActionContext:
    return ActionContext(
        pipeline_name="p",
        run_id="run-1",
        params={"template": "code", "diff": "HEAD~1", **params},
        step_name="review",
        step_index=0,
        prior_outputs={},
        resolver=resolver or ModelResolver(),
        cf_client=MagicMock(),
        cwd=str(repo),
        usage_capture=UsageCapture(set()),
        recipe_sink=sink,
    )


async def _execute(context: ActionContext) -> ActionResult:
    return await ReviewAction().execute(context)


def _recipe_ref(repo: Path) -> RecipeRef:
    path = repo / PROJECT_RECIPES_DIR / f"{RECIPE_NAME}.yaml"
    return RecipeRef(recipe=load_recipe(path), path=path)


def _review_files(repo: Path) -> list[Path]:
    return sorted((repo / REVIEWS_DIR).glob("*.md"))


def _recipe_metadata(result: ActionResult) -> dict[str, object]:
    metadata = result.metadata[RECIPE_METADATA_KEY]
    assert isinstance(metadata, dict)
    return cast(dict[str, object], metadata)


def _record(sink: FakeRecipeSink) -> RecipeReview:
    ((record, _raw),) = sink.writes
    return record


# --- D9 usage record ---------------------------------------------------------------


def _stages(tmp_path: Path, **overrides: list[Scripted]) -> tuple[RecipeStageResult, ...]:
    recipe = load_recipe(_recipe_file(tmp_path))
    return run_scripted(recipe, ScriptedReviewCall(_script(**overrides)), tmp_path).stages


def _recipe_file(tmp_path: Path) -> Path:
    path = tmp_path / "recipes" / f"{RECIPE_NAME}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(RECIPE_TEXT, encoding="utf-8")
    return path


def test_usage_record_all_priced(repo: Path, tmp_path: Path) -> None:
    record = recipe_usage_record(RECIPE_NAME, _stages(tmp_path))
    assert record.alias == RECIPE_NAME and record.model is None
    assert record.cost_usd is not None and round(record.cost_usd, 6) == round(2 * 0.01 + 4 * 0.002, 6)
    assert record.turns == 6 and record.duration_seconds == 12.0


def test_usage_record_one_unpriced_is_a_floor_and_warns(
    repo: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    stages = _stages(tmp_path, **{"comb-2": [comb(("F1", "KEEP"), cost=None)]})
    with caplog.at_level(logging.WARNING, logger="squadron.pipeline.actions.review_recipe"):
        record = recipe_usage_record(RECIPE_NAME, stages)
    assert record.cost_usd is not None and round(record.cost_usd, 6) == round(2 * 0.01 + 2 * 0.002, 6)
    (warning,) = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert "comb rev-a > comb-1 > comb-2" in warning and "comb rev-b > comb-1 > comb-2" in warning


def test_usage_record_none_priced_has_no_cost(repo: Path, tmp_path: Path) -> None:
    script: dict[str, list[Scripted]] = {
        "rev-a": [review_result([A1], cost=None)],
        "rev-b": [review_result([B_FAIL], Verdict.FAIL, cost=None)],
        "comb-1": [comb(("F1", "KEEP"), cost=None)],
        "comb-2": [comb(("F1", "KEEP"), cost=None)],
    }
    assert recipe_usage_record(RECIPE_NAME, _stages(tmp_path, **script)).cost_usd is None


def test_usage_record_mixed_bases_is_none(repo: Path, tmp_path: Path) -> None:
    provider, alias = review_result([A1]), review_result([B_FAIL], Verdict.FAIL)
    provider.cost_basis, alias.cost_basis = CostBasis.PROVIDER, CostBasis.ALIAS_PRICING
    stages = _stages(tmp_path, **{"rev-a": [provider], "rev-b": [alias]})
    assert recipe_usage_record(RECIPE_NAME, stages).cost_basis is None
    same = _stages(tmp_path / "same", **{"rev-a": [provider], "rev-b": [provider]})
    only_reviews = [s for s in same if s.kind.value == "review"]
    assert recipe_usage_record(RECIPE_NAME, only_reviews).cost_basis is CostBasis.PROVIDER


# --- success path --------------------------------------------------------------------


@pytest.mark.parametrize("via", ["action_model", "pipeline_model"])
@pytest.mark.asyncio
async def test_recipe_name_runs_the_recipe(
    repo: Path, monkeypatch: pytest.MonkeyPatch, via: str
) -> None:
    scripted = _scripted(monkeypatch)
    sink = FakeRecipeSink()
    if via == "action_model":
        context = _context(repo, sink, model=RECIPE_NAME)
    else:
        context = _context(repo, sink, ModelResolver(pipeline_model=RECIPE_NAME))
    result = await _execute(context)
    assert result.success and result.verdict == Verdict.FAIL.value
    assert len(scripted.calls) == 6
    record = _record(sink)
    assert result.metadata[RECIPE_METADATA_KEY] == {
        "name": RECIPE_NAME,
        "complete": True,
        "record_id": record.record_id,
    }
    usage = result.metadata[USAGE_KEY]
    assert isinstance(usage, dict) and usage["alias"] == RECIPE_NAME and usage["model"] is None
    assert record.run_id == "run-1" and record.step_name == "review" and record.iteration is None
    (review_file,) = _review_files(repo)
    assert record.review_file == str(review_file)
    text = review_file.read_text(encoding="utf-8")
    assert f"aiModel: {RECIPE_NAME}" in text and "aiRecipe: true" in text and "## Recipe" in text
    comb_calls = [c for c in scripted.calls if c.alias.startswith("comb")]
    assert all(c.inputs["changed_files"] == "src/app.py" for c in comb_calls)


@pytest.mark.asyncio
async def test_failing_input_validation_makes_no_stage_call(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripted = _scripted(monkeypatch)
    sink = FakeRecipeSink()
    result = await _execute(_context(repo, sink, model=RECIPE_NAME, input="missing.md"))
    assert not result.success and "missing.md" in (result.error or "")
    assert scripted.calls == [] and sink.writes == []


@pytest.mark.asyncio
async def test_recipe_with_explicit_profile_is_refused_at_execution(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripted = _scripted(monkeypatch)
    result = await _execute(_context(repo, FakeRecipeSink(), model=RECIPE_NAME, profile="openrouter"))
    assert not result.success and "profile 'openrouter' is refused" in (result.error or "")
    assert scripted.calls == []


# --- D5 failed stages through the action ------------------------------------------------


@pytest.mark.asyncio
async def test_one_reviewer_fails_and_a_concern_is_kept_succeeds_with_fail(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _scripted(monkeypatch, **{"rev-b": [provider_error("quota exceeded")]})
    sink = FakeRecipeSink()
    result = await _execute(_context(repo, sink, model=RECIPE_NAME))
    assert result.success and result.verdict == Verdict.FAIL.value
    assert _recipe_metadata(result)["complete"] is False
    text = _review_files(repo)[0].read_text(encoding="utf-8")
    assert "harness_failure" in text and "quota exceeded" in text and "recipeComplete: false" in text
    record = _record(sink)
    assert not record.complete
    assert [s.outcome for s in record.stages if s.alias == "rev-b"] == [StageOutcome.HARNESS_FAILURE]


@pytest.mark.parametrize(
    "overrides",
    [
        {"rev-a": [provider_error()], "comb-1": [comb(("F1", "DROP"))]},  # nothing kept
        {"rev-a": [provider_error()], "rev-b": [provider_error()]},  # every reviewer fails
    ],
)
@pytest.mark.asyncio
async def test_incomplete_with_nothing_kept_fails_and_still_writes_file_and_record(
    repo: Path, monkeypatch: pytest.MonkeyPatch, overrides: dict[str, list[Scripted]]
) -> None:
    _scripted(monkeypatch, **overrides)
    sink = FakeRecipeSink()
    result = await _execute(_context(repo, sink, model=RECIPE_NAME))
    assert not result.success and result.verdict == Verdict.UNKNOWN.value
    assert "review rev-a" in (result.error or "")
    assert USAGE_KEY in result.metadata
    assert len(_review_files(repo)) == 1
    record = _record(sink)
    assert record.verdict is Verdict.UNKNOWN and not record.complete


@pytest.mark.asyncio
async def test_failed_comb_keeps_input_marked_and_next_comb_runs(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripted = _scripted(monkeypatch, **{"comb-1": [provider_error("comb down"), comb(("F1", "KEEP"))]})
    sink = FakeRecipeSink()
    result = await _execute(_context(repo, sink, model=RECIPE_NAME))
    assert result.success and scripted.aliases()[:3] == ["rev-a", "comb-1", "comb-2"]
    text = _review_files(repo)[0].read_text(encoding="utf-8")
    assert "not combed: comb-1 failed" in text and "recipeComplete: false" in text
    record = _record(sink)
    assert record.stages[1].outcome is StageOutcome.HARNESS_FAILURE and not record.complete


@pytest.mark.asyncio
async def test_partial_decisions_are_kept_as_undecided_and_complete(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    two = review_result([A1, review_finding("a2")])
    _scripted(monkeypatch, **{"rev-a": [two], "comb-1": [comb(("F1", "KEEP"))]})
    sink = FakeRecipeSink()
    result = await _execute(_context(repo, sink, model=RECIPE_NAME))
    text = _review_files(repo)[0].read_text(encoding="utf-8")
    assert "### [CONCERN] a2" in text and "undecided 1" in text
    assert _recipe_metadata(result)["complete"] is True
    assert _record(sink).complete


@pytest.mark.asyncio
async def test_repeated_and_unknown_ids_are_counted_and_warned(
    repo: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    noisy = comb(("F1", "KEEP"), ("F1", "DROP"), ("F7", "KEEP"))
    _scripted(monkeypatch, **{"comb-1": [noisy, comb(("F1", "KEEP"))]})
    sink = FakeRecipeSink()
    with caplog.at_level(logging.WARNING, logger="squadron.recipes.recipe_runner"):
        await _execute(_context(repo, sink, model=RECIPE_NAME))
    stage = _record(sink).stages[1]
    assert (stage.duplicate_decisions, stage.unknown_ids) == (1, 1)
    assert stage.decisions["F1"].verdict.value == "KEEP"
    assert any("repeated 1" in r.getMessage() and "1 unknown" in r.getMessage() for r in caplog.records)
    assert "comb rev-a > comb-1" in _review_files(repo)[0].read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_unexpected_exception_writes_aborted_record_and_stamps_spend(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _scripted(monkeypatch, **{"rev-b": [RuntimeError("parse bug")]})
    sink = FakeRecipeSink()
    result = await _execute(_context(repo, sink, model=RECIPE_NAME))
    assert not result.success and result.error == "parse bug"
    usage = result.metadata[USAGE_KEY]
    assert isinstance(usage, dict) and usage["cost_usd"] == pytest.approx(0.01 + 2 * 0.002)
    assert _record(sink).aborted == "parse bug" and _review_files(repo) == []


@pytest.mark.asyncio
async def test_empty_scope_makes_no_call_and_no_record(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripted = _scripted(monkeypatch)
    sink = FakeRecipeSink()
    result = await _execute(_context(repo, sink, model=RECIPE_NAME, diff="HEAD..HEAD"))
    assert not result.success and scripted.calls == [] and sink.writes == []


# --- executor: loops and the cost cap -------------------------------------------------------


def _loop_pipeline(loop: dict[str, object]) -> PipelineDefinition:
    step = StepConfig(
        step_type="review",
        name="review",
        config={"template": "code", "model": RECIPE_NAME, "loop": loop},
    )
    return PipelineDefinition(name="recipe-loop", description="t", params={}, steps=[step])


async def _run_pipeline(
    repo: Path, definition: PipelineDefinition, sink: FakeRecipeSink
) -> PipelineResult:
    return await execute_pipeline(
        definition,
        {"diff": "HEAD~1"},
        resolver=ModelResolver(),
        cf_client=MagicMock(),  # type: ignore[arg-type]
        cwd=str(repo),
        runs_dir=repo / "runs",
        recipe_sink=sink,
    )


@pytest.mark.asyncio
async def test_revise_loop_runs_every_stage_in_each_round(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripted = _scripted(monkeypatch)
    sink = FakeRecipeSink()
    result = await _run_pipeline(repo, _loop_pipeline({"max": 2, "until": "review.pass"}), sink)
    assert result.status is ExecutionStatus.FAILED  # FAIL both rounds: exhausted
    assert len(scripted.calls) == 12
    assert [r.iteration for r, _ in sink.writes] == [1, 2]


@pytest.mark.asyncio
async def test_incomplete_last_round_is_never_accepted(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    concern_only = review_result([B1])
    _scripted(monkeypatch, **{"rev-a": [provider_error()], "rev-b": [concern_only]})
    loop: dict[str, object] = {
        "max": 1,
        "until": "review.pass",
        "accept_if": "review.concerns_or_better",
    }
    result = await _run_pipeline(repo, _loop_pipeline(loop), FakeRecipeSink())
    (step,) = result.step_results
    assert step.exhausted and not step.accepted
    assert step.status is ExecutionStatus.FAILED
    assert step.action_results[0].verdict == Verdict.FAIL.value


@pytest.mark.parametrize("unpriced", [False, True])
@pytest.mark.asyncio
async def test_cost_cap_below_the_recipe_total_stops_the_run(
    repo: Path, monkeypatch: pytest.MonkeyPatch, unpriced: bool
) -> None:
    set_config(COST_CAP_KEY, "0.01", project=True, cwd=str(repo))
    overrides = {"comb-2": [comb(("F1", "KEEP"), cost=None)]} if unpriced else {}
    _scripted(monkeypatch, **overrides)
    step = StepConfig(
        step_type="review", name="review", config={"template": "code", "model": RECIPE_NAME}
    )
    after = StepConfig(
        step_type="review", name="never", config={"template": "code", "model": RECIPE_NAME}
    )
    definition = PipelineDefinition(name="cap", description="t", params={}, steps=[step, after])
    result = await _run_pipeline(repo, definition, FakeRecipeSink())
    assert result.status is ExecutionStatus.FAILED
    assert [s.step_name for s in result.step_results] == ["review"]
    failed = result.step_results[-1].action_results[0]
    assert failed.metadata[FAILURE_KIND_KEY] == FailureKind.COST_CAP.value
    spent = 2 * 0.01 + (2 if unpriced else 4) * 0.002
    assert f"run spent ${spent:.2f}" in (failed.error or "")


@pytest.mark.asyncio
async def test_aborted_part_stamps_the_spend_of_earlier_parts(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A later part's abort must not drop what the earlier parts spent (D9)."""
    _scripted(monkeypatch, **{"rev-b": [review_result([B_FAIL], Verdict.FAIL), RuntimeError("bug")]})
    context = _context(repo, FakeRecipeSink())
    spent: list[RecipeStageResult] = []
    part = RecipePart(
        ref=_recipe_ref(repo),
        template=builtin_template("code"),
        inputs={"cwd": str(repo), "diff": "HEAD~1"},
        rules_content=None,
        allowed_tools=None,
        changed_files=["src/app.py"],
        spent=spent,
    )

    async def save(result: ReviewResult) -> str | None:
        return None

    def to_result(result: ReviewResult, review_file: str | None) -> ActionResult:
        return ActionResult(
            success=True, action_type="review", outputs={}, verdict=result.verdict.value
        )

    await run_recipe_part(part, context, save=save, to_action_result=to_result, pricing_warned=set())
    with pytest.raises(RecipePartAborted) as raised:
        await run_recipe_part(
            part, context, save=save, to_action_result=to_result, pricing_warned=set()
        )
    record = raised.value.record
    assert record is not None and record.cost_usd is not None
    # Part 1: two reviews and four combs; part 2: rev-a and its two combs before rev-b raised.
    assert record.cost_usd == pytest.approx(2 * 0.01 + 4 * 0.002 + 0.01 + 2 * 0.002)


def test_usage_record_counts_failed_stage_spend_and_ignores_silent_failures(
    repo: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    spent = _stages(tmp_path / "spent", **{"rev-b": [provider_error_with_spend(cost=0.03)]})
    record = recipe_usage_record(RECIPE_NAME, spent)
    assert record.cost_usd == pytest.approx(0.01 + 2 * 0.002 + 0.03)
    assert record.usage.prompt == 500
    silent = _stages(tmp_path / "silent", **{"rev-b": [provider_error()]})
    with caplog.at_level(logging.WARNING, logger="squadron.pipeline.actions.review_recipe"):
        record = recipe_usage_record(RECIPE_NAME, silent)
    assert record.cost_usd == pytest.approx(0.01 + 2 * 0.002)
    adapter = "squadron.pipeline.actions.review_recipe"
    assert not [r for r in caplog.records if r.name == adapter]  # not "unpriced"


@pytest.mark.asyncio
async def test_tool_less_recipe_step_is_refused_before_any_call(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripted = _scripted(monkeypatch)
    result = await _execute(_context(repo, FakeRecipeSink(), model=RECIPE_NAME, allowed_tools=[]))
    assert not result.success and "tool-less review" in (result.error or "")
    assert scripted.calls == []
