"""The shared recipe review flow: save then record, aborts, cancellation (slice 434, D5, D8)."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from squadron.core.finding_categories import ReviewCategory
from squadron.metrology.content_sidecars import ContentSidecars, SidecarKind
from squadron.metrology.errors import MetrologyIdentityError, MetrologyStoreError
from squadron.metrology.models import RECORD_TYPE_RECIPE_REVIEW
from squadron.metrology.project_id import ProjectId, ProjectIdSource
from squadron.metrology.recall_run_models import StageKind, StageOutcome
from squadron.metrology.recipe_review_models import RecipeReview
from squadron.metrology.store import MetrologyStore
from squadron.recipes.comb_call import ReviewCall, call_comb
from squadron.recipes.kept_findings import split_by_category
from squadron.recipes.recipe import Recipe
from squadron.recipes.recipe_record import (
    MetrologyStoreRecipeSink,
    RecipeRecordContext,
    RecipeRecordSink,
)
from squadron.recipes.recipe_review import (
    CANCELLED_REASON,
    RecipeReviewOutput,
    RecipeReviewRequest,
    run_recipe_review,
)
from squadron.recipes.recipe_runner import RecipeReviewCall
from squadron.recipes.stage_config import builtin_template
from squadron.review.models import ReviewResult, Severity, Verdict
from squadron.review.templates import ReviewTemplate
from tests.recipes.support import (
    FakeRecipeSink,
    Scripted,
    ScriptedReviewCall,
    decisions_text,
    review_finding,
    review_result,
)

LOGGER = "squadron.recipes.recipe_review"
NOW = datetime(2026, 11, 19, 12, 0, tzinfo=UTC)
CONTEXT = RecipeRecordContext(
    project_id=lambda: ProjectId(value="github.com/x/y", source=ProjectIdSource.REMOTE),
    clock=lambda: NOW,
)


def comb(*pairs: tuple[str, str]) -> Scripted:
    return review_result([], Verdict.PASS, raw=decisions_text(*pairs))


def _script() -> dict[str, list[Scripted]]:
    return {
        "rev-a": [review_result([review_finding("a1")])],
        "rev-b": [review_result([review_finding("b1")])],
        "comb-1": [comb(("F1", "KEEP"))],
        "comb-2": [comb(("F1", "KEEP"))],
    }


def _request(recipe: Recipe, scripted: ReviewCall, cwd: Path) -> RecipeReviewRequest:
    call = RecipeReviewCall(
        template=builtin_template("code"),
        inputs={"cwd": str(cwd), "diff": "HEAD~1"},
        options={},
        review_call=scripted,
        comb_call=call_comb,
    )
    return RecipeReviewRequest(
        recipe=recipe,
        call=call,
        changed_files=["src/app.py"],
        cwd=cwd,
        input_files={"diff": "HEAD~1"},
        slow_after_s=60,
    )


class Saver:
    def __init__(self, events: list[str], path: Path | None, fail: bool = False) -> None:
        self.events = events
        self.path = path
        self.fail = fail
        self.saved: list[ReviewResult] = []

    async def __call__(self, result: ReviewResult) -> Path | None:
        self.events.append("save")
        if self.fail:
            raise OSError("reviews dir is read-only")
        self.saved.append(result)
        return self.path


class OrderedSink(FakeRecipeSink):
    def __init__(self, events: list[str], fail_with: type[BaseException] | None = None) -> None:
        super().__init__(fail_with=fail_with)
        self.events = events

    def write(self, record: RecipeReview, raw_outputs: dict[str, str]) -> None:  # type: ignore[override]
        self.events.append("record")
        super().write(record, raw_outputs)


def _run(
    recipe: Recipe,
    tmp_path: Path,
    saver: Saver,
    sink: RecipeRecordSink,
    script: dict[str, list[Scripted]],
) -> RecipeReviewOutput:
    request = _request(recipe, ScriptedReviewCall(script), tmp_path)
    return asyncio.run(run_recipe_review(request, save=saver, sink=sink, context=CONTEXT))


def test_save_then_record(recipe: Recipe, tmp_path: Path) -> None:
    events: list[str] = []
    sink = OrderedSink(events)
    output = _run(recipe, tmp_path, Saver(events, tmp_path / "r.md"), sink, _script())
    assert events == ["save", "record"]
    ((record, raw),) = sink.writes
    assert output.record_id == record.record_id and record.review_file == str(tmp_path / "r.md")
    assert record.complete and record.aborted is None and len(record.stages) == 6
    assert {s.raw_ref for s in record.stages} == set(raw)


def test_save_raises_records_with_no_file_and_propagates(recipe: Recipe, tmp_path: Path) -> None:
    events: list[str] = []
    sink = OrderedSink(events)
    with pytest.raises(OSError, match="read-only"):
        _run(recipe, tmp_path, Saver(events, None, fail=True), sink, _script())
    assert events == ["save", "record"]
    assert sink.writes[0][0].review_file is None


@pytest.mark.parametrize("error", [MetrologyStoreError, OSError])
def test_sink_failure_logs_error_and_returns_the_result(
    recipe: Recipe, tmp_path: Path, caplog: pytest.LogCaptureFixture, error: type[BaseException]
) -> None:
    events: list[str] = []
    with caplog.at_level(logging.ERROR, logger=LOGGER):
        output = _run(recipe, tmp_path, Saver(events, None), OrderedSink(events, error), _script())
    assert output.record_id is None and output.result.verdict is Verdict.CONCERNS
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1 and "rrev-" in errors[0] and "not written" in errors[0]


def test_unexpected_exception_writes_aborted_record_and_no_save(
    recipe: Recipe, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    events: list[str] = []
    sink = OrderedSink(events)
    script = _script()
    script["rev-b"] = [RuntimeError("parse bug")]
    with caplog.at_level(logging.ERROR, logger=LOGGER), pytest.raises(RuntimeError, match="parse bug"):
        _run(recipe, tmp_path, Saver(events, None), sink, script)
    assert events == ["record"]
    record = sink.writes[0][0]
    assert record.aborted == "parse bug" and not record.complete and record.verdict is Verdict.UNKNOWN
    assert [s.alias for s in record.stages] == ["rev-a", "comb-1", "comb-2"]
    assert record.review_file is None
    assert any(r.levelno == logging.ERROR and r.exc_info for r in caplog.records)


def test_cancellation_writes_aborted_record_synchronously_and_propagates(
    recipe: Recipe, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    events: list[str] = []
    sink = OrderedSink(events)
    script = _script()
    script["rev-b"] = [asyncio.CancelledError()]
    request = _request(recipe, ScriptedReviewCall(script), tmp_path)

    async def drive() -> None:
        await run_recipe_review(request, save=Saver(events, None), sink=sink, context=CONTEXT)

    with caplog.at_level(logging.WARNING, logger=LOGGER), pytest.raises(asyncio.CancelledError):
        asyncio.run(drive())
    assert events == ["record"]
    record = sink.writes[0][0]
    assert record.aborted == CANCELLED_REASON and [s.alias for s in record.stages] == [
        "rev-a",
        "comb-1",
        "comb-2",
    ]
    assert any(r.levelno == logging.WARNING and "cancelled" in r.getMessage() for r in caplog.records)


def test_cancellation_write_error_is_logged_and_cancellation_propagates(
    recipe: Recipe, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    script = _script()
    script["rev-a"] = [asyncio.CancelledError()]
    request = _request(recipe, ScriptedReviewCall(script), tmp_path)
    sink = FakeRecipeSink(fail_with=OSError)
    with caplog.at_level(logging.ERROR, logger=LOGGER), pytest.raises(asyncio.CancelledError):
        asyncio.run(run_recipe_review(request, save=Saver([], None), sink=sink, context=CONTEXT))
    assert any(r.levelno == logging.ERROR and "not written" in r.getMessage() for r in caplog.records)


def test_metrology_store_sink_writes_record_and_sidecar(recipe: Recipe, tmp_path: Path) -> None:
    store = MetrologyStore(tmp_path / "store")
    output = _run(recipe, tmp_path, Saver([], None), MetrologyStoreRecipeSink(lambda: store), _script())
    ((record_id, envelope),) = list(store.iter_records())
    assert record_id == output.record_id and envelope.record_type == RECORD_TYPE_RECIPE_REVIEW
    assert envelope.recipe_review is not None
    stage = envelope.recipe_review.stages[0]
    assert stage.raw_ref is not None
    sidecar = ContentSidecars(store.store_dir, SidecarKind.REVIEWS)
    assert json.loads(sidecar.get(stage.raw_ref))["raw_output"] == "raw review"


def test_no_project_identity_is_a_record_write_failure(
    recipe: Recipe, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    def no_identity() -> ProjectId:
        raise MetrologyIdentityError("no remote, no recorded id")

    context = RecipeRecordContext(project_id=no_identity, clock=lambda: NOW)
    request = _request(recipe, ScriptedReviewCall(_script()), tmp_path)
    sink = FakeRecipeSink()
    with caplog.at_level(logging.ERROR, logger=LOGGER):
        output = asyncio.run(
            run_recipe_review(request, save=Saver([], None), sink=sink, context=context)
        )
    assert output.record_id is None and sink.writes == []
    assert any("no remote" in r.getMessage() for r in caplog.records if r.levelno == logging.ERROR)


def test_a_real_cancellation_writes_the_aborted_record(recipe: Recipe, tmp_path: Path) -> None:
    """The task running the recipe is cancelled while a stage call is in flight."""
    sink = FakeRecipeSink()
    scripted = ScriptedReviewCall(_script(), delay_s=5.0)
    started = asyncio.Event()

    async def call(template: ReviewTemplate, inputs: dict[str, str], **kwargs: Any) -> ReviewResult:
        started.set()
        return await scripted(template, inputs, **kwargs)

    request = _request(recipe, call, tmp_path)

    async def drive() -> None:
        task = asyncio.create_task(
            run_recipe_review(request, save=Saver([], None), sink=sink, context=CONTEXT)
        )
        await started.wait()
        task.cancel()
        await task

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(drive())
    ((record, _raw),) = sink.writes
    assert record.aborted == CANCELLED_REASON and record.stages == []


CORRECT = ReviewCategory.CORRECTNESS.value
DEBT = ReviewCategory.TEST_DEBT.value


def _filter_script() -> dict[str, list[Scripted]]:
    return {
        "rev-a": [
            review_result(
                [
                    review_finding("a-gate", Severity.CONCERN, CORRECT),
                    review_finding("a-debt", Severity.CONCERN, DEBT),
                ]
            )
        ],
        # An UNKNOWN verdict: its findings are recorded but the runner uses none of them.
        "rev-b": [review_result([review_finding("b-gate", Severity.FAIL, CORRECT)], Verdict.UNKNOWN)],
    }


def _record_for(recipe: Recipe, tmp_path: Path, script: dict[str, list[Scripted]]) -> RecipeReview:
    sink = FakeRecipeSink()
    _run(recipe, tmp_path, Saver([], tmp_path / "r.md"), sink, script)
    ((record, _),) = sink.writes
    return record


def test_record_carries_the_filter_or_none(tmp_path: Path, recipe_aliases: object) -> None:
    with_filter = Recipe(
        name="f", reviewers=("rev-a", "rev-b"), keep_categories=(ReviewCategory.CORRECTNESS,)
    )
    without = Recipe(name="g", reviewers=("rev-a", "rev-b"))
    script = _filter_script()
    assert _record_for(with_filter, tmp_path, script).keep_categories == (ReviewCategory.CORRECTNESS,)
    assert _record_for(without, tmp_path, script).keep_categories is None


def test_split_over_the_record_reproduces_the_runners_gating_set(
    tmp_path: Path, recipe_aliases: object
) -> None:
    recipe = Recipe(
        name="f", reviewers=("rev-a", "rev-b"), keep_categories=(ReviewCategory.CORRECTNESS,)
    )
    sink = FakeRecipeSink()
    request = _request(recipe, ScriptedReviewCall(_filter_script()), tmp_path)
    output = asyncio.run(
        run_recipe_review(request, save=Saver([], tmp_path / "r.md"), sink=sink, context=CONTEXT)
    )
    ((record, _),) = sink.writes
    from_record = [
        finding.title
        for stage in record.stages
        if stage.kind is StageKind.REVIEW and stage.outcome is StageOutcome.OK
        for finding in split_by_category(stage.findings, record.keep_categories)[0]
    ]
    gating = [f.title for f in output.result.findings]
    assert from_record == gating == ["a-gate"]
    unknown_stage = record.stages[1]
    assert unknown_stage.outcome is not StageOutcome.OK and [
        f.title for f in unknown_stage.findings
    ] == ["b-gate"]
